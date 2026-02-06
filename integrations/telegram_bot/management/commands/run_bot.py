"""
Telegram Bot Management Command - The main chat interface for SecureAssist.
"""
import asyncio
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from agents.orchestrator.agent import orchestrator_agent

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
        application.add_handler(msg_handler)
        application.add_handler(voice_handler)
        
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        # Keep running
        while True:
            await asyncio.sleep(1)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.message.text:
            return

        user_id = f"tg_{update.effective_user.id}"
        session_id = f"tg_session_{update.effective_chat.id}"
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
            user_id = f"tg_{update.effective_user.id}"
            session_id = f"tg_session_{update.effective_chat.id}"
            
            await update.message.reply_text(f"✨ *Transcribed*: _{transcription}_", parse_mode="Markdown")
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

            result = await orchestrator_agent.process(
                user_id=user_id,
                message=f"[VOICE INGESTION]: {transcription}",
                session_id=session_id
            )

            # 5. Reply
            await update.message.reply_text(result.response, parse_mode="Markdown")

        except Exception as e:
            logger.exception("Error in voice handler")
            await update.message.reply_text(f"❌ Voice processing failed: {str(e)}")
