from django.db import models


class TelegramUser(models.Model):
    """Maps a SecureAssist user_id to a Telegram chat_id."""
    user_id = models.CharField(max_length=100, unique=True, db_index=True)
    chat_id = models.BigIntegerField(db_index=True)
    username = models.CharField(max_length=150, blank=True, null=True)
    first_name = models.CharField(max_length=150, blank=True, null=True)
    last_name = models.CharField(max_length=150, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.user_id} -> {self.chat_id}"
