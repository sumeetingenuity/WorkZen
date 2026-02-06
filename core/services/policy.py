"""
Policy Engine - Access control and rate limiting for tools.
"""
import re
import logging
from typing import Dict, Any, Optional
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class PolicyEngine:
    """
    Enforces security policies before tool execution.
    """
    
    async def check_permission(
        self,
        tool_name: str,
        input_data: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> bool:
        """Check if tool execution is permitted."""
        from core.models import ToolPolicy
        
        try:
            policy = await sync_to_async(ToolPolicy.objects.get)(tool_name=tool_name)
        except ToolPolicy.DoesNotExist:
            return True  # No policy = default allow
        
        if not policy.enabled:
            logger.warning(f"Tool {tool_name} is disabled")
            return False
        
        if policy.allowed_users and user_id:
            if user_id not in policy.allowed_users:
                logger.warning(f"User {user_id} not allowed for tool {tool_name}")
                return False
        
        if not await self._check_rate_limit(tool_name, user_id, policy.rate_limit):
            logger.warning(f"Rate limit exceeded for {tool_name}")
            return False
        
        if policy.blocked_inputs:
            input_str = str(input_data)
            for pattern in policy.blocked_inputs:
                if re.search(pattern, input_str, re.IGNORECASE):
                    logger.warning(f"Blocked pattern matched for {tool_name}")
                    return False
        
        return True
    
    async def _check_rate_limit(
        self,
        tool_name: str,
        user_id: Optional[str],
        limit: int
    ) -> bool:
        """Check rate limit using cache."""
        if limit <= 0:
            return True
        
        try:
            from django.core.cache import cache
            from datetime import datetime
            
            user_key = user_id or 'anonymous'
            hour_bucket = datetime.now().strftime('%Y%m%d%H')
            key = f"ratelimit:{tool_name}:{user_key}:{hour_bucket}"
            
            current = cache.get(key, 0)
            if current >= limit:
                return False
            
            cache.set(key, current + 1, 3600)
            return True
            
        except Exception as e:
            logger.warning(f"Rate limit check failed: {e}")
            return True
    
    async def requires_approval(self, tool_name: str) -> bool:
        """Check if a tool requires user approval."""
        from core.models import ToolPolicy
        
        try:
            policy = await sync_to_async(ToolPolicy.objects.get)(tool_name=tool_name)
            return policy.requires_approval
        except ToolPolicy.DoesNotExist:
            return False
