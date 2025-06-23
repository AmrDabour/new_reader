from elevenlabs.client import ElevenLabs
from ..config import (
    ELEVENLABS_API_KEY,
    ELEVENLABS_ENGLISH_VOICE_ID,
    ELEVENLABS_ARABIC_VOICE_ID,
    ARABIC_NUMBER_MAP
)
from typing import Optional
import requests
from word2number import w2n
from ..config import get_settings
from ..utils.arabic import is_arabic_text

settings = get_settings()

class SpeechService:
    def __init__(self):
        self.client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        self.is_available = True

    def text_to_speech(self, text: str, voice_id: Optional[str] = None, language_direction: str = "ltr") -> Optional[bytes]:
        """
        Convert text to speech using ElevenLabs
        """
        try:
            # Determine which voice to use
            if not voice_id:
                voice_id = (
                    ELEVENLABS_ARABIC_VOICE_ID 
                    if language_direction == "rtl" or is_arabic_text(text)
                    else ELEVENLABS_ENGLISH_VOICE_ID
                )
            
            # Generate audio stream
            audio_stream = self.client.text_to_speech.stream(
                text=text,
                voice_id=voice_id,
                model_id="eleven_multilingual_v2"
            )

            # Get audio bytes from the generator
            return b"".join(chunk for chunk in audio_stream)

        except Exception as e:
            print(f"Error in text-to-speech service: {e}")
            return None

    def speech_to_text(self, audio_bytes: bytes, language_code: str = 'en') -> Optional[str]:
        """
        Convert audio to text using ElevenLabs
        """
        try:
            url = "https://api.elevenlabs.io/v1/speech-to-text"
            headers = {
                "xi-api-key": ELEVENLABS_API_KEY
            }
            files = {
                'file': ('audio.wav', audio_bytes, 'audio/wav')
            }
            data = {
                "model_id": "scribe_v1",
                "language_code": language_code,
                "tag_audio_events": False,
                "temperature": 0.0
            }

            response = requests.post(url, headers=headers, files=files, data=data)
            response.raise_for_status()
            result = response.json()
            return result.get("text", "")

        except Exception as e:
            print(f"Error in speech-to-text service: {e}")
            return None

    def process_transcript(self, text: str, lang: str) -> str:
        """
        Process transcript by converting number words to digits
        """
        # Strip punctuation and whitespace
        processed_text = text.strip(".,;:\"'")
        
        # Convert number words to digits
        words = processed_text.split()
        
        if lang == 'en':
            try:
                return str(w2n.word_to_num(processed_text))
            except ValueError:
                converted_words = []
                for word in words:
                    try:
                        converted_words.append(str(w2n.word_to_num(word)))
                    except ValueError:
                        converted_words.append(word)
                return " ".join(converted_words)
        
        elif lang == 'ar':
            converted_words = []
            for word in words:
                converted_words.append(ARABIC_NUMBER_MAP.get(word, word))
            
            # Join adjacent digits
            final_text = []
            for i, word in enumerate(converted_words):
                is_digit = word.isdigit()
                is_prev_digit = (i > 0 and converted_words[i-1].isdigit())
                
                if is_digit and is_prev_digit:
                    final_text[-1] += word
                else:
                    final_text.append(word)
            
            return " ".join(final_text)
        
        return " ".join(words) 