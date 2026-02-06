"""
Capability Registry - Central registry for all agent capabilities.

Auto-discovers tools from Django apps and maintains a JSON registry
that is injected into the orchestrator's context.
"""
import json
import importlib
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from django.conf import settings

logger = logging.getLogger(__name__)


class CapabilityRegistry:
    """
    Central registry for all agent capabilities.
    
    This is what makes the agent "universal" - it knows what it can do
    by querying this registry, not by hardcoded knowledge.
    """
    
    _instance = None
    _registry: Dict[str, dict] = {}
    _tools: Dict[str, Callable] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._registry = {}
            cls._instance._tools = {}
        return cls._instance
    
    def register_tool(self, func: Callable) -> None:
        """Register a tool function decorated with @agent_tool."""
        if not hasattr(func, '_tool_meta'):
            raise ValueError("Function must be decorated with @agent_tool")
        
        meta = func._tool_meta
        name = meta['name']
        category = meta['category']
        
        self._tools[name] = func
        
        if category not in self._registry:
            self._registry[category] = {
                'app': func.__module__.split('.')[0] if hasattr(func, '__module__') else 'unknown',
                'tools': [],
                'requires': []
            }
        
        existing = [t['name'] for t in self._registry[category]['tools']]
        if name not in existing:
            self._registry[category]['tools'].append({
                'name': meta['name'],
                'description': meta['description'],
                'input_schema': meta['input_schema'],
                'requires_approval': meta['requires_approval'],
            })
            
            for secret in meta.get('secrets', []):
                if secret not in self._registry[category]['requires']:
                    self._registry[category]['requires'].append(secret)
            
            logger.info(f"Registered tool: {name} in category: {category}")
        
        self._save_registry()
    
    def discover_tools(self) -> None:
        """Scan all Django apps for @agent_tool decorated functions."""
        try:
            from django.apps import apps
            
            for app_config in apps.get_app_configs():
                if app_config.name.startswith('django.'):
                    continue
                
                try:
                    tools_module = importlib.import_module(f'{app_config.name}.tools')
                    for name in dir(tools_module):
                        obj = getattr(tools_module, name)
                        if hasattr(obj, '_tool_meta'):
                            self.register_tool(obj)
                except ImportError:
                    pass
                except Exception as e:
                    logger.warning(f"Error discovering tools in {app_config.name}: {e}")
        except Exception as e:
            logger.warning(f"Could not discover tools: {e}")
    
    def _save_registry(self) -> None:
        """Persist registry to JSON file."""
        try:
            registry_path = Path(settings.BASE_DIR) / 'capability_registry.json'
            registry_path.write_text(json.dumps(self._registry, indent=2))
        except Exception as e:
            logger.warning(f"Could not save registry: {e}")
    
    def get_for_llm(self) -> str:
        """Get compact registry for LLM context injection."""
        compact = {}
        for category, data in self._registry.items():
            compact[category] = {
                'tools': [t['name'] for t in data['tools']],
                'descriptions': {
                    t['name']: t['description'][:100]
                    for t in data['tools']
                }
            }
        return json.dumps(compact, separators=(',', ':'))
    
    def get_full_registry(self) -> Dict[str, dict]:
        """Get complete registry."""
        return self._registry.copy()
    
    def get_tool(self, tool_name: str) -> Optional[Callable]:
        """Get a tool function by name."""
        return self._tools.get(tool_name)
    
    def get_tool_schema(self, tool_name: str) -> Optional[dict]:
        """Get full schema for a specific tool."""
        for cap_data in self._registry.values():
            for tool in cap_data['tools']:
                if tool['name'] == tool_name:
                    return tool
        return None
    
    def list_tools(self) -> List[str]:
        """List all registered tool names."""
        return list(self._tools.keys())
    
    def get_tools_by_names(self, tool_names: List[str]) -> Dict[str, Callable]:
        """Get tool functions by their names."""
        return {name: self._tools[name] for name in tool_names if name in self._tools}

    def list_tools_schema(self, tool_names: Optional[List[str]] = None) -> List[dict]:
        """List full schemas for specific tools or all tools."""
        schemas = []
        for cap_data in self._registry.values():
            for tool in cap_data['tools']:
                if tool_names is None or tool['name'] in tool_names:
                    schemas.append(tool)
        return schemas


# Singleton instance
capability_registry = CapabilityRegistry()
