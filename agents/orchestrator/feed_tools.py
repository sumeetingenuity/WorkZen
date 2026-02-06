"""
Intelligence Feed Tools - Agent-callable tools for proactive web monitoring.
"""
import logging
from core.decorators import agent_tool
from core.services.intelligence import intelligence_feed_service
from core.models import IntelligenceFeed

logger = logging.getLogger(__name__)

@agent_tool(
    name="subscribe_to_intelligence_feed",
    description="Subscribe to a topic or URL for proactive monitoring and alerts.",
    category="system"
)
async def subscribe_to_intelligence_feed(topic: str, frequency: str = "daily", _user_id: str = None):
    """Subscribes to an intelligence feed."""
    feed = await intelligence_feed_service.subscribe(_user_id, topic, frequency)
    return {
        "status": "subscribed",
        "topic": topic,
        "frequency": frequency,
        "feed_id": str(feed.id)
    }

@agent_tool(
    name="list_intelligence_feeds",
    description="List all active intelligence feeds for the current user.",
    category="system"
)
async def list_intelligence_feeds(_user_id: str = None):
    """Lists intelligence feeds."""
    feeds = []
    async for f in IntelligenceFeed.objects.filter(user_id=_user_id, is_active=True):
        feeds.append({
            "id": str(f.id),
            "topic": f.topic,
            "frequency": f.frequency,
            "last_checked": f.last_checked_at.isoformat() if f.last_checked_at else "never"
        })
    return {"feeds": feeds}

@agent_tool(
    name="unsubscribe_from_feed",
    description="Deactivate an intelligence feed.",
    category="system"
)
async def unsubscribe_from_feed(feed_id: str, _user_id: str = None):
    """Unsubscribes from a feed."""
    try:
        feed = await IntelligenceFeed.objects.aget(id=feed_id, user_id=_user_id)
        feed.is_active = False
        await feed.asave()
        return {"status": "deactivated", "topic": feed.topic}
    except IntelligenceFeed.DoesNotExist:
        return {"status": "error", "message": f"Feed '{feed_id}' not found."}
