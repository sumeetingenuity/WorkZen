"""
Telegram Bot Management Command - The main chat interface for SecureAssist.
"""
import asyncio
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters
from agents.orchestrator.agent import orchestrator_agent
from core.services.git_service import git_service

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Starts the SecureAssist Telegram Bot'

    def handle(self, *args, **options):
        token = settings.TELEGRAM_BOT_TOKEN
        if not token or token == "YOUR_TELEGRAM_BOT_TOKEN":
            self.stdout.write(self.style.ERROR('Telegram token not configured. Run "python onboard.py" first.'))
            return

        self.stdout.write(self.style.SUCCESS('🚀 Starting SecureAssist Telegram Bot...'))
        
        # Run the async bot
        asyncio.run(self.run_bot(token))

    async def run_bot(self, token):
        self.secret_requests = {} # Track user_id -> secret_name
        application = ApplicationBuilder().token(token).build()
        
        msg_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message)
        voice_handler = MessageHandler(filters.VOICE, self.handle_voice)
        image_handler = MessageHandler(filters.PHOTO | filters.Document.IMAGE, self.handle_image)
        document_handler = MessageHandler(filters.Document.ALL & (~filters.Document.IMAGE), self.handle_document)
        video_handler = MessageHandler(filters.VIDEO | filters.ANIMATION, self.handle_video)
        status_handler = CommandHandler("git_status", self.handle_git_status)
        rollback_handler = CommandHandler("rollback", self.handle_rollback)
        
        application.add_handler(msg_handler)
        application.add_handler(voice_handler)
        application.add_handler(image_handler)
        application.add_handler(document_handler)
        application.add_handler(video_handler)
        application.add_handler(status_handler)
        application.add_handler(rollback_handler)
        
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        # Keep running
        while True:
            await asyncio.sleep(1)

    async def _upsert_telegram_user(self, update: Update):
        try:
            from asgiref.sync import sync_to_async
            from integrations.telegram_bot.models import TelegramUser

            user_id = f"tg_{update.effective_user.id}"
            chat_id = update.effective_chat.id
            username = update.effective_user.username
            first_name = update.effective_user.first_name
            last_name = update.effective_user.last_name

            async def _save():
                obj, _ = TelegramUser.objects.update_or_create(
                    user_id=user_id,
                    defaults={
                        "chat_id": chat_id,
                        "username": username,
                        "first_name": first_name,
                        "last_name": last_name
                    }
                )
                return obj

            await sync_to_async(_save)()
        except Exception:
            pass

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.message.text:
            return

        await self._upsert_telegram_user(update)

        import uuid
        
        user_id = f"tg_{update.effective_user.id}"
        # Generate a deterministic valid UUID from the chat ID
        session_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"tg_session_{update.effective_chat.id}"))
        message_text = update.message.text

        # Handle pending secret input
        if user_id in self.secret_requests:
            secret_name = self.secret_requests.pop(user_id)
            from core.services.secrets import SecretEngine
            se = SecretEngine()
            await se.set_secret(secret_name, message_text)
            
            # Delete the secret input message for security
            try:
                await update.message.delete()
            except Exception:
                pass
                
            await update.message.reply_text(f"✅ Securely stored: `{secret_name}`. You can now resume your request.", parse_mode="Markdown")
            return

        # 1. Show "typing..."
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        try:
            # 2. Process via Orchestrator
            result = await orchestrator_agent.process(
                user_id=user_id,
                message=message_text,
                session_id=session_id
            )

            # 3. Handle result highlights (approvals, etc)
            response_text = result.response
            
            # Check for WAITING_FOR_SECRET signal in tool outputs
            # This logic assumes the orchestrator adds tool_outputs to the result or we peek into it
            # For now, we'll check if the response mentions the signal or if we can peek into the execution record
            if "WAITING_FOR_SECRET" in response_text or getattr(result, 'wait_for_secret', False):
                 # Look for metadata in the result if available
                 secret_name = result.metadata.get("secret_name") if hasattr(result, "metadata") else None
                 if secret_name:
                     self.secret_requests[user_id] = secret_name
                     response_text += f"\n\n🔐 *ACTION REQUIRED*: Please paste the value for `{secret_name}` below. Your message will be deleted after processing."
            
            if result.requires_approval:
                response_text += f"\n\n🔐 *Approval Required*: {result.pending_task_id}"

            # 4. Reply
            await update.message.reply_text(response_text, parse_mode="Markdown")

        except Exception as e:
            logger.exception("Error in telegram handler")
            await update.message.reply_text(f"❌ System error: {str(e)}")

    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Processes voice messages: Download -> Transcribe -> Orchestrate."""
        if not update.message or not update.message.voice:
            return

        await self._upsert_telegram_user(update)

        # 1. State: Transcribing
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="record_voice")
        
        try:
            # 2. Download file
            import os
            import tempfile
            file = await context.bot.get_file(update.message.voice.file_id)
            
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
                await file.download_to_drive(tmp.name)
                tmp_path = tmp.name

            # 3. Transcribe
            from agents.model_router import model_router
            transcription = await model_router.transcribe(tmp_path)
            
            # Cleanup
            os.remove(tmp_path)
            
            if not transcription:
                await update.message.reply_text("🔇 I couldn't hear anything in that message.")
                return

            # 4. Route to Orchestrator (wrapped in a note about it being voice)
            import uuid
            user_id = f"tg_{update.effective_user.id}"
            session_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"tg_session_{update.effective_chat.id}"))
            
            await update.message.reply_text(f"✨ *Transcribed*: _{transcription}_", parse_mode="Markdown")
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

            result = await orchestrator_agent.process(
                user_id=user_id,
                message=f"[VOICE INGESTION]: {transcription}",
                session_id=session_id
            )

            # 5. Reply
            await update.message.reply_text(result.response)

        except Exception as e:
            logger.exception("Error in voice handler")
            await update.message.reply_text(f"❌ Voice processing failed: {str(e)}")

    async def handle_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Processes image messages: Download -> Store -> Orchestrate."""
        if not update.message:
            return

        photo = None
        file_name = "image"
        if update.message.photo:
            photo = update.message.photo[-1]
        elif update.message.document and update.message.document.mime_type:
            if update.message.document.mime_type.startswith("image/"):
                photo = update.message.document
                file_name = update.message.document.file_name or "image"
        if not photo:
            return

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        try:
            import os
            import tempfile
            from apps.storage.tools import store_document
            import uuid

            file = await context.bot.get_file(photo.file_id)
            suffix = os.path.splitext(file_name)[1] or ".jpg"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                await file.download_to_drive(tmp.name)
                tmp_path = tmp.name

            upload_result = await store_document(
                file_path=tmp_path,
                file_type="image",
                original_name=file_name,
                mime_type=getattr(photo, "mime_type", "") or "image/jpeg",
                description=f"Telegram upload: {file_name}",
                user_id=f"tg_{update.effective_user.id}",
                session_id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"tg_session_{update.effective_chat.id}"))
            )
            os.remove(tmp_path)
            stored_path = upload_result.get("path") if isinstance(upload_result, dict) else None
            if not stored_path:
                error_msg = upload_result.get("error") if isinstance(upload_result, dict) else "Unknown error"
                await update.message.reply_text(f"❌ Failed to store image: {error_msg}")
                return

            user_id = f"tg_{update.effective_user.id}"
            session_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"tg_session_{update.effective_chat.id}"))

            await update.message.reply_text(f"🖼️ Image stored at: `{stored_path}`", parse_mode="Markdown")
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

            caption = update.message.caption or ""
            message = f"[FILE STORED]\nType: image\nName: {file_name}\nPath: {stored_path}\nCaption: {caption}\nNote: Stored only. Processing happens only on request."
            result = await orchestrator_agent.process(
                user_id=user_id,
                message=message,
                session_id=session_id
            )
            await update.message.reply_text(result.response)
        except Exception as e:
            logger.exception("Error in image handler")
            await update.message.reply_text(f"❌ Image processing failed: {str(e)}")

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Processes documents (pdf, csv, xls, etc.)."""
        if not update.message or not update.message.document:
            return

        await self._upsert_telegram_user(update)

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        try:
            import os
            import tempfile
            from apps.storage.tools import store_document

            doc = update.message.document
            file_name = doc.file_name or "document"
            mime_type = doc.mime_type or "application/octet-stream"

            file = await context.bot.get_file(doc.file_id)
            suffix = os.path.splitext(file_name)[1] or ".bin"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                await file.download_to_drive(tmp.name)
                tmp_path = tmp.name

            upload_result = await store_document(
                file_path=tmp_path,
                file_type=file_type,
                original_name=file_name,
                mime_type=mime_type,
                description=f"Telegram upload: {file_name}",
                user_id=f"tg_{update.effective_user.id}",
                session_id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"tg_session_{update.effective_chat.id}"))
            )
            os.remove(tmp_path)
            stored_path = upload_result.get("path") if isinstance(upload_result, dict) else None
            if not stored_path:
                error_msg = upload_result.get("error") if isinstance(upload_result, dict) else "Unknown error"
                await update.message.reply_text(f"❌ Failed to store document: {error_msg}")
                return

            file_type = "document"
            ext = os.path.splitext(file_name)[1].lower()
            if mime_type.startswith("image/") or ext in {".png", ".jpg", ".jpeg", ".webp"}:
                file_type = "image"
            elif ext == ".pdf" or mime_type == "application/pdf":
                file_type = "pdf"
            elif ext in {".csv"}:
                file_type = "csv"
            elif ext in {".xls", ".xlsx"}:
                file_type = "spreadsheet"

            import uuid
            user_id = f"tg_{update.effective_user.id}"
            session_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"tg_session_{update.effective_chat.id}"))

            caption = update.message.caption or ""
            message = f"[FILE STORED]\nType: {file_type}\nName: {file_name}\nMime: {mime_type}\nPath: {stored_path}\nCaption: {caption}\nNote: Stored only. Processing happens only on request."

            await update.message.reply_text(f"📎 Document stored at: `{stored_path}`", parse_mode="Markdown")
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

            result = await orchestrator_agent.process(
                user_id=user_id,
                message=message,
                session_id=session_id
            )
            await update.message.reply_text(result.response)
        except Exception as e:
            logger.exception("Error in document handler")
            await update.message.reply_text(f"❌ Document processing failed: {str(e)}")

    async def handle_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Processes video and animation files by storing and notifying."""
        if not update.message:
            return

        video = update.message.video or update.message.animation
        if not video:
            return

        await self._upsert_telegram_user(update)

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        try:
            import os
            import tempfile
            from apps.storage.tools import store_document

            file_name = getattr(video, "file_name", None) or "video"
            mime_type = getattr(video, "mime_type", None) or "video/mp4"

            file = await context.bot.get_file(video.file_id)
            suffix = os.path.splitext(file_name)[1] or ".mp4"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                await file.download_to_drive(tmp.name)
                tmp_path = tmp.name

            upload_result = await store_document(
                file_path=tmp_path,
                file_type="video",
                original_name=file_name,
                mime_type=mime_type,
                description=f"Telegram upload: {file_name}",
                user_id=f"tg_{update.effective_user.id}",
                session_id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"tg_session_{update.effective_chat.id}"))
            )
            os.remove(tmp_path)
            stored_path = upload_result.get("path") if isinstance(upload_result, dict) else None
            if not stored_path:
                error_msg = upload_result.get("error") if isinstance(upload_result, dict) else "Unknown error"
                await update.message.reply_text(f"❌ Failed to store video: {error_msg}")
                return

            import uuid
            user_id = f"tg_{update.effective_user.id}"
            session_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"tg_session_{update.effective_chat.id}"))

            caption = update.message.caption or ""
            message = f"[FILE STORED]\nType: video\nName: {file_name}\nMime: {mime_type}\nPath: {stored_path}\nCaption: {caption}\nNote: Stored only. Processing happens only on request."

            await update.message.reply_text(f"🎞️ Video stored at: `{stored_path}`", parse_mode="Markdown")
            result = await orchestrator_agent.process(
                user_id=user_id,
                message=message,
                session_id=session_id
            )
            await update.message.reply_text(result.response, parse_mode="Markdown")
        except Exception as e:
            logger.exception("Error in video handler")
            await update.message.reply_text(f"❌ Video processing failed: {str(e)}")

    async def handle_git_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current git status."""
        status = git_service.get_status()
        await update.message.reply_text(f"📂 *Current Development Status*:\n\n`{status or 'Clean codebase'}`", parse_mode="Markdown")

    async def handle_rollback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Revert to the previous checkpoint."""
        # Simple confirmation if no arg provided
        success = git_service.rollback()
        if success:
            await update.message.reply_text("🔙 *Rollback Successful*. Codebase reverted to the last stable checkpoint.", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Rollback failed.")
