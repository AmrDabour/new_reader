import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from app.config import get_settings
import io
import wave
import os
from pathlib import Path

settings = get_settings()

class SpeechService:
    def __init__(self):
        """Initializes separate Gemini models for multimodal and TTS tasks."""
        try:
            # Configure genai with the key from settings
            genai.configure(api_key=settings.google_ai_api_key)
            self.multimodal_model = genai.GenerativeModel("gemini-2.5-flash")
            self.tts_model = genai.GenerativeModel("gemini-2.5-flash-preview-tts")
            self.is_available = True
        except Exception as e:
            self.multimodal_model = None
            self.tts_model = None
            self.is_available = False
            print(f"Fatal: Could not initialize Gemini models for speech: {e}")

    def text_to_speech(self, text: str, provider: str = "gemini"):
        """Converts text to speech using the gemini-2.5-flash-preview-tts model."""
        if provider != "gemini" or not self.is_available or not self.tts_model or not text:
            return None, None
        
        try:
            is_arabic = any('\u0600' <= char <= '\u06FF' for char in text)
            voice_name = "Sulafat" if is_arabic else "Kore"

            response = self.tts_model.generate_content(
                f"Read this: {text}",
                generation_config={
                   "response_modalities": ["AUDIO"],
                   "speech_config": {
                      "voice_config": {
                         "prebuilt_voice_config": { "voice_name": voice_name }
                      }
                   }
                }
            )
            audio_data = response.candidates[0].content.parts[0].inline_data.data

            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(audio_data)
            
            return wav_buffer.getvalue(), "audio/wav"
        except google_exceptions.ResourceExhausted as e:
            print(f"Gemini API Quota Exceeded for TTS: {e}")
            return "QUOTA_EXCEEDED", "error"
        except Exception as e:
            print(f"Gemini Text-to-Speech Error: {e}")
            return None, None

    def speech_to_text(self, audio_bytes: bytes, language_code: str = 'en'):
        """
        Converts audio to text, forcing transcription in the specified language.
        """
        if not self.is_available or not self.multimodal_model or not audio_bytes:
            return None

        try:
            audio_part = {"mime_type": "audio/wav", "data": audio_bytes}
            
            lang_name = "Arabic" if language_code == 'ar' else "English"
            prompt = f"You are a highly accurate audio transcription service. You must transcribe the following audio recording in {lang_name}. Ignore all non-speech sounds like [noise] or [music] and provide only the clean text of the spoken words."
            
            response = self.multimodal_model.generate_content([prompt, audio_part])
            return response.text.strip()
            
        except google_exceptions.ResourceExhausted as e:
            print(f"Gemini API Quota Exceeded: {e}")
            return "QUOTA_EXCEEDED"
        except Exception as e:
            print(f"Gemini Speech-to-Text Error: {e}")
            return None 