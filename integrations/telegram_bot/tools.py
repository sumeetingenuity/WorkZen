"""
Telegram Tools for SecureAssist.
"""
import os
import httpx
from core.decorators import agent_tool
from django.conf import settings
from integrations.telegram_bot.models import TelegramUser


@agent_tool(
    name="send_telegram_file",
    description="Send a stored file to the user's Telegram chat.",
    log_response_to_orm=True,
    category="communication"
)
async def send_telegram_file(file_path: str, caption: str = "", user_id: str = "") -> dict:
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}

    if not user_id:
        return {"error": "user_id is required to route the file to Telegram."}

    try:
        tg_user = TelegramUser.objects.get(user_id=user_id)
    except TelegramUser.DoesNotExist:
        return {"error": f"No Telegram chat linked for user_id {user_id}"}

    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return {"error": "TELEGRAM_BOT_TOKEN not configured"}

    url = f"https://api.telegram.org/bot{token}/sendDocument"
    async with httpx.AsyncClient() as client:
        with open(file_path, "rb") as f:
            files = {"document": f}
            data = {"chat_id": tg_user.chat_id, "caption": caption}
            resp = await client.post(url, data=data, files=files, timeout=60.0)
            if resp.status_code != 200:
                return {"error": f"Telegram send failed: {resp.text}"}

    return {"status": "sent", "chat_id": tg_user.chat_id, "file_path": file_path}
