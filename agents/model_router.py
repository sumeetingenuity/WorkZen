"""
Model Router - Routes LLM requests to appropriate models.

Uses litellm for unified interface across providers.
"""
import logging
import os
from typing import Literal, Optional
from django.conf import settings

logger = logging.getLogger(__name__)

TaskType = Literal["orchestrate", "summarize", "code", "tool", "vision", "embed", "tts", "stt"]


def async_retry(max_retries: int = 3, initial_delay: float = 1.0, backoff_factor: float = 2.0):
    """
    Decorator for async functions to retry on exception with exponential backoff.
    """
    from functools import wraps
    import asyncio
    import random

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt == max_retries:
                        logger.error(f"Function {func.__name__} failed after {max_retries} retries. Error: {e}")
                        raise e
                    
                    # Log and wait
                    wait_time = delay * (1 + random.random() * 0.1) # Add 10% jitter
                    logger.warning(f"Attempt {attempt + 1}/{max_retries} for {func.__name__} failed: {e}. Retrying in {wait_time:.2f}s...")
                    await asyncio.sleep(wait_time)
                    delay *= backoff_factor
            
            raise last_exception
        return wrapper
    return decorator


class ModelRouter:
    """
    Routes requests to appropriate LLM based on task type.
    
    Uses litellm for unified interface across OpenAI, Anthropic, Google, etc.
    """
    
    def __init__(self):
        self._models = settings.LLM_CONFIG
    
    def get_model(self, task_type: TaskType) -> str:
        """Get the configured model for a task type."""
        return self._models.get(task_type, self._models.get('tool', 'openai/gpt-4o'))

    async def get_model_async(self, task_type: TaskType, agent_name: Optional[str] = None) -> str:
        """
        Get the configured model, checking for agent-specific overrides.
        """
        if agent_name:
            try:
                from core.models import CustomAgent
                from asgiref.sync import sync_to_async
                agent = await sync_to_async(CustomAgent.objects.filter(name=agent_name).first)()
                if agent and agent.model_id:
                    return agent.model_id
            except Exception as e:
                logger.warning(f"Failed to fetch agent model override for {agent_name}: {e}")

        return self.get_model(task_type)
    
    async def complete(
        self,
        task_type: TaskType,
        messages: list[dict],
        response_model=None,
        max_tokens: int = 4096,
        agent_name: Optional[str] = None
    ):
        """
        Route completion request to appropriate model.
        Automatic validation retries enabled for structured outputs.
        """
        try:
            return await self._execute_complete(task_type, messages, response_model, max_tokens, agent_name)
        except Exception as e:
            logger.error(f"Final model completion failure: {e}")
            raise e

    @async_retry(max_retries=3)
    async def _execute_complete(
        self,
        task_type: TaskType,
        messages: list[dict],
        response_model=None,
        max_tokens: int = 4096,
        agent_name: Optional[str] = None
    ):
        try:
            from litellm import acompletion
            
            model = await self.get_model_async(task_type, agent_name)
            logger.debug(f"Routing {task_type} to model: {model} (Agent: {agent_name or 'Default'})")
            
            if response_model:
                # Use instructor for guaranteed structured output
                try:
                    import instructor
                    client = instructor.from_litellm(acompletion)
                    extra_kwargs = {}
                    if model.startswith("openrouter/"):
                        extra_kwargs["tool_choice"] = "auto"
                    return await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        response_model=response_model,
                        max_tokens=max_tokens,
                        max_retries=2, # Instructor internal retries for validation errors
                        **extra_kwargs
                    )
                except ImportError:
                    logger.warning("instructor not installed, falling back to raw completion")
                except Exception as e:
                    # Handle XML/entity parsing errors from malformed LLM responses
                    error_str = str(e).lower()
                    if "parse entity" in error_str or "xml" in error_str or "entity" in error_str or "byte offset" in error_str:
                        logger.warning(f"XML/entity parsing error in structured output, falling back to raw completion: {e}")
                        return await acompletion(
                            model=model,
                            messages=messages,
                            max_tokens=max_tokens
                        )
                    raise e
            
            return await acompletion(
                model=model,
                messages=messages,
                max_tokens=max_tokens
            )
            
        except ImportError:
            logger.error("litellm not installed")
            raise ImportError("litellm is required for LLM routing")
    
    async def summarize(self, text: str, max_length: int = 200) -> str:
        """Quick summarization using fast model."""
        response = await self.complete(
            task_type="summarize",
            messages=[{
                "role": "user",
                "content": f"Summarize in {max_length} chars:\n\n{text}"
            }],
            max_tokens=100
        )
        return response.choices[0].message.content

    async def embed(self, text: str) -> list[float]:
        """Get embeddings for a string."""
        try:
            model = self.get_model("embed")
            if model.startswith("ollama/"):
                import httpx
                base_url = os.environ.get("LITELLM_LOCAL_BASE_URL", "http://localhost:11434").rstrip("/")
                model_name = model.split("/", 1)[1]
                async with httpx.AsyncClient() as client:
                    # Newer Ollama endpoint
                    embed_url = f"{base_url}/api/embed"
                    try:
                        response = await client.post(
                            embed_url,
                            json={"model": model_name, "input": text},
                            timeout=30.0
                        )
                        if response.status_code == 200:
                            data = response.json()
                            if "embedding" in data:
                                return data["embedding"]
                            if "data" in data and data["data"]:
                                return data["data"][0].get("embedding", [])
                        # Fall through to legacy endpoint if not supported
                    except httpx.HTTPStatusError:
                        pass
                    # Legacy Ollama endpoint
                    legacy_url = f"{base_url}/api/embeddings"
                    response = await client.post(
                        legacy_url,
                        json={"model": model_name, "prompt": text},
                        timeout=30.0
                    )
                    response.raise_for_status()
                    data = response.json()
                    if "embedding" in data:
                        return data["embedding"]
                    if "data" in data and data["data"]:
                        return data["data"][0].get("embedding", [])
                    raise ValueError("Ollama embedding response missing embedding data")

            from litellm import aembedding
            response = await aembedding(model=model, input=[text])
            return response.data[0]["embedding"]
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            raise e

    async def speak(self, text: str) -> bytes:
        """Convert text to speech."""
        try:
            model = self.get_model("tts")
            if model == "local/vibevoice":
                from core.services.tts_local import local_tts
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp_path = tmp.name
                
                success = await local_tts.speak(text, tmp_path)
                if success:
                    with open(tmp_path, "rb") as f:
                        data = f.read()
                    import os
                    os.remove(tmp_path)
                    return type('Response', (), {'content': data})
                else:
                    raise Exception("Local TTS synthesis failed")

            from litellm import text_to_speech
            voice = getattr(settings, "LLM_TTS_VOICE", "alloy")
            response = await text_to_speech(
                model=model,
                input=text,
                voice=voice
            )
            return response.content
        except Exception as e:
            logger.error(f"TTS failed: {e}")
            raise e

    async def transcribe(self, audio_file: str) -> str:
        """Convert speech to text."""
        try:
            from litellm import transcription
            model = self.get_model("stt")
            with open(audio_file, "rb") as f:
                response = await transcription(
                    model=model,
                    file=f
                )
            return response.text
        except Exception as e:
            logger.error(f"STT failed: {e}")
            raise e


# Singleton instance
model_router = ModelRouter()
