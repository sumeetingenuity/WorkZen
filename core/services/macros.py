"""
Macro Tool Manager - Enables tool composition.

Allows the AI to combine multiple existing tools into a single named 'Macro'.
"""
import logging
import json
import os
from typing import List, Dict, Any, Optional
from django.conf import settings

logger = logging.getLogger(__name__)

class MacroToolManager:
    """
    Manages composition of tools into high-level macros.
    """
    
    def __init__(self):
        self.macro_file = os.path.join(settings.BASE_DIR, "data", "macros.json")
        os.makedirs(os.path.dirname(self.macro_file), exist_ok=True)
        self.macros = self._load_macros()
    
    def _load_macros(self) -> Dict[str, Any]:
        if os.path.exists(self.macro_file):
            try:
                with open(self.macro_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def _save_macros(self):
        with open(self.macro_file, 'w') as f:
            json.dump(self.macros, f, indent=2)
            
    def register_macro(self, name: str, description: str, steps: List[Dict[str, Any]]):
        """
        Register a new macro tool.
        Steps: [{"tool": "name", "mapping": {"macro_arg": "tool_arg"}}]
        """
        self.macros[name] = {
            "name": name,
            "description": description,
            "steps": steps,
            "category": "macros"
        }
        self._save_macros()
        logger.info(f"Registered macro: {name}")
        
    def get_macro(self, name: str) -> Optional[Dict[str, Any]]:
        return self.macros.get(name)

# Singleton
macro_manager = MacroToolManager()
