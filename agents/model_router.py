"""
Model Router - Routes LLM requests to appropriate models.

Uses litellm for unified interface across providers.
"""
import logging
from typing import Literal, Optional
from django.conf import settings

logger = logging.getLogger(__name__)

TaskType = Literal["orchestrate", "summarize", "code", "tool", "vision", "embed", "tts", "stt"]


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
        
        Args:
            task_type: Type of task to determine model
            messages: Chat messages
            response_model: Pydantic model for structured output
            max_tokens: Max response tokens
        """
        try:
            from litellm import acompletion
            
            model = await self.get_model_async(task_type, agent_name)
            logger.debug(f"Routing {task_type} to model: {model} (Agent: {agent_name or 'Default'})")
            
            if response_model:
                # Use instructor for guaranteed structured output
                try:
                    import instructor
                    client = instructor.from_litellm(acompletion)
                    return await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        response_model=response_model,
                        max_tokens=max_tokens
                    )
                except ImportError:
                    logger.warning("instructor not installed, falling back to raw completion")
            
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
            from litellm import aembedding
            model = self.get_model("embed")
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
