"""
Briefing Service - Generates daily status reports and activity sweeps.
"""
import logging
import datetime
from django.conf import settings
from core.models import AuditLog, ToolResponse
from agents.model_router import model_router

logger = logging.getLogger(__name__)

class BriefingService:
    """
    Sweeps daily activity and generates summarized briefings.
    """
    
    async def generate_daily_report(self, user_id: str):
        """
        Gathers today's logs and generates a summary report.
        """
        today = datetime.datetime.now().date()
        
        # 1. Fetch activity logs
        logs = AuditLog.objects.filter(
            user_id=user_id,
            created_at__date=today
        ).order_by('created_at')
        
        # 2. Extract action summaries
        activity_text = []
        async for log in logs:
            activity_text.append(f"- {log.action}: {log.tool or 'Query'} ({log.status})")
        
        if not activity_text:
            return "No significant activity found for today."

        # 3. Use AI to synthesize the briefing
        prompt = f"""Summarize today's agent activity into a concise, professional briefing for the user.
Identity: {getattr(settings, 'AGENT_NAME', 'SecureAssist')}
Persona: {getattr(settings, 'AGENT_PERSONA', 'Professional')}

Activity Logs:
{chr(10).join(activity_text)}

Focus on:
- Major tasks completed (e.g., App building, Research)
- Success rate
- Pending actions for tomorrow.
"""
        try:
            response = await model_router.complete(
                task_type="summarize",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Briefing generation failed: {e}")
            return "Failed to generate briefing. Activity log is available in the audit dashboard."

briefing_service = BriefingService()
