"""
Webhook Service.

Handles triggering external webhooks for agent events.
"""
import json
import httpx
import hmac
import hashlib
import logging
from typing import Any, Dict, Optional
from django.conf import settings
from core.models import Webhook

logger = logging.getLogger(__name__)

class WebhookService:
    """
    Manages and triggers external webhooks.
    """
    
    async def trigger(self, user_id: str, event_type: str, payload: Dict[str, Any]):
        """Trigger webhooks for a specific event type."""
        webhooks = Webhook.objects.filter(user_id=user_id, is_active=True)
        
        # Filtrate webhooks that listen to this event type
        active_hooks = []
        async for hook in webhooks:
            if event_type in hook.event_types or "*" in hook.event_types:
                active_hooks.append(hook)
        
        if not active_hooks:
            return
            
        async with httpx.AsyncClient() as client:
            for hook in active_hooks:
                try:
                    # Prepare headers and signature
                    headers = {"Content-Type": "application/json"}
                    body = json.dumps({
                        "event": event_type,
                        "payload": payload
                    })
                    
                    if hook.secret:
                        signature = hmac.new(
                            hook.secret.encode(),
                            body.encode(),
                            hashlib.sha256
                        ).hexdigest()
                        headers["X-SecureAssist-Signature"] = signature
                    
                    response = await client.post(
                        hook.url,
                        content=body,
                        headers=headers,
                        timeout=5.0
                    )
                    
                    if response.status_code >= 400:
                        logger.warning(f"Webhook {hook.name} failed with status {response.status_code}")
                        
                except Exception as e:
                    logger.error(f"Failed to trigger webhook {hook.name}: {e}")

webhook_service = WebhookService()
