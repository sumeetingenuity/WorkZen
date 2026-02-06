"""
Intelligence Feed Service - Proactive web monitoring and alert system.
"""
import logging
import datetime
from core.models import IntelligenceFeed
from apps.web_research.tools import search_web
from core.services.scheduler import scheduler_service

logger = logging.getLogger(__name__)

class IntelligenceFeedService:
    """
    Manages proactive information gathering.
    """
    
    async def subscribe(self, user_id: str, topic: str, frequency: str = "daily"):
        """Adds a new intelligence feed."""
        feed = await IntelligenceFeed.objects.acreate(
            user_id=user_id,
            topic=topic,
            frequency=frequency
        )
        logger.info(f"Subscribed to Intelligence Feed: {topic} ({frequency})")
        return feed

    async def check_all_feeds(self):
        """
        Background task to iterate over active feeds and perform research.
        This is typically called by a cron job or background worker.
        """
        active_feeds = IntelligenceFeed.objects.filter(is_active=True)
        async for feed in active_feeds:
            logger.info(f"Checking Intelligence Feed: {feed.topic}...")
            # Perform search
            results = await search_web(query=feed.topic, max_results=3)
            
            # TODO: In a full implementation, we would compare results with past checks
            # and only notify if "new/significant" data is found.
            # For now, we update the last_checked_at.
            feed.last_checked_at = datetime.datetime.now()
            await feed.asave()
            
            logger.info(f"Feed '{feed.topic}' updated with {len(results.get('results', []))} matches.")

intelligence_feed_service = IntelligenceFeedService()
