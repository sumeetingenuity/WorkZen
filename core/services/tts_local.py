"""
Local TTS Service using microsoft/VibeVoice-1.5B.
"""
import os
import torch
import logging
import soundfile as sf
from typing import Optional
from django.conf import settings

logger = logging.getLogger(__name__)

class LocalTTSService:
    """
    Handles local text-to-speech using microsoft/VibeVoice-1.5B.
    """
    
    _instance = None
    _model = None
    _processor = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LocalTTSService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_id = "microsoft/VibeVoice-1.5B"
        self.cache_dir = os.path.expanduser("~/.secureassist/models")
        os.makedirs(self.cache_dir, exist_ok=True)

    def _load_model(self):
        """Lazy load the model to save memory."""
        if self._model is None:
            try:
                from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq
                logger.info(f"Loading {self.model_id} onto {self.device}...")
                
                # VibeVoice usually requires specific loading logic if not standard SpeechSeq2Seq
                # For this implementation, we assume it follow standard transformer patterns
                # or provide a clear path for customization.
                self._processor = AutoProcessor.from_pretrained(self.model_id, cache_dir=self.cache_dir)
                self._model = AutoModelForSpeechSeq2Seq.from_pretrained(
                    self.model_id, 
                    cache_dir=self.cache_dir,
                    torch_dtype=torch.float16 if self.device == "cuda" else torch.float32
                ).to(self.device)
                
                logger.info("Local TTS model loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load local TTS model: {e}")
                raise e

    async def speak(self, text: str, output_path: str) -> bool:
        """
        Synthesize speech from text and save to file.
        """
        try:
            self._load_model()
            
            # Simple inference loop (this is a placeholder for VibeVoice specific logic)
            # VibeVoice-1.5B might have a custom 'generate' method or requires specific inputs
            inputs = self._processor(text=text, return_tensors="pt").to(self.device)
            
            with torch.no_grad():
                # Placeholder for VibeVoice generation
                # In practice, VibeVoice might return a waveform directly
                speech = self._model.generate(**inputs)
            
            # Save to wav
            waveform = speech.cpu().numpy().squeeze()
            sf.write(output_path, waveform, self._processor.feature_extractor.sampling_rate)
            
            return True
        except Exception as e:
            logger.error(f"TTS Synthesis failed: {e}")
            return False

# Singleton instance
local_tts = LocalTTSService()
