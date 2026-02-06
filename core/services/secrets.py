"""
Secret Engine - Runtime-only secret injection.

Secrets are NEVER exposed to LLMs or stored in context.
"""
import os
import logging
from typing import Optional, Any
from django.conf import settings

logger = logging.getLogger(__name__)


class SecretEngine:
    """
    Runtime-only secret injection.
    
    Secrets are injected only at the moment of tool execution,
    then immediately cleared.
    """
    
    def __init__(self):
        self._cache = {}
        self._masked_values = set()
        self.vault_path = os.path.expanduser("~/.secureassist/vault.json")
        self._load_vault()

    def _load_vault(self):
        """Load secrets from the secure out-of-workspace vault."""
        import json
        if os.path.exists(self.vault_path):
            try:
                with open(self.vault_path, 'r') as f:
                    self._vault = json.load(f)
                    logger.info("Secure vault loaded from ~/.secureassist/vault.json")
            except Exception as e:
                logger.error(f"Failed to load vault: {e}")
                self._vault = {}
        else:
            self._vault = {}
    
    async def get(self, secret_name: str) -> Optional[str]:
        """Get secret value at runtime, prioritizing the secure vault."""
        if secret_name in self._cache:
            return self._cache[secret_name]
        
        value = None
        
        # Priority 1: Secure Vault (Out-of-workspace)
        value = self._vault.get(secret_name)
        
        # Priority 2: Environment variable (Fallback)
        if not value:
            value = os.environ.get(secret_name)
        
        # Priority 3: Django settings (Fallback)
        if not value:
            value = getattr(settings, secret_name, None)
        
        if value:
            self._cache[secret_name] = value
            self._masked_values.add(str(value))
            logger.debug(f"Secret loaded: {secret_name}")
        else:
            logger.warning(f"Secret not found: {secret_name}")
        
        return value

    async def set_secret(self, secret_name: str, value: str) -> bool:
        """Securely store a secret in the vault."""
        try:
            import json
            self._vault[secret_name] = value
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.vault_path), exist_ok=True)
            
            with open(self.vault_path, 'w') as f:
                json.dump(self._vault, f, indent=2)
            
            # Set strict permissions
            if os.name != 'nt':
                os.chmod(self.vault_path, 0o600)
            
            # Update cache
            self._cache[secret_name] = value
            self._masked_values.add(str(value))
            
            logger.info(f"Secret '{secret_name}' stored securely in vault.")
            return True
        except Exception as e:
            logger.error(f"Failed to store secret {secret_name}: {e}")
            return False
    
    def mask_in_output(self, output: Any) -> Any:
        """Remove any leaked secrets from output."""
        if not self._masked_values:
            return output
        
        if isinstance(output, str):
            return self._mask_string(output)
        elif isinstance(output, dict):
            return {k: self.mask_in_output(v) for k, v in output.items()}
        elif isinstance(output, list):
            return [self.mask_in_output(v) for v in output]
        else:
            return output
    
    def _mask_string(self, text: str) -> str:
        """Mask all known secret values in a string."""
        masked = text
        for secret_value in self._masked_values:
            if secret_value and secret_value in masked:
                masked = masked.replace(secret_value, '[REDACTED]')
        return masked
    
    def clear_cache(self):
        """Clear cached secrets."""
        self._cache.clear()
        self._masked_values.clear()
