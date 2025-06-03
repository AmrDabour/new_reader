import os
import traceback
from elevenlabs.client import ElevenLabs
from elevenlabs import play
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = "9BWtsMINqrJLrRacOk9x"  # Aria

elevenlabs = ElevenLabs(api_key=API_KEY)

def speak_field(text):
    print(f"Using ELEVENLABS_API_KEY: {'SET' if API_KEY else 'NOT SET'}")
    if not API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY is not set.")
    try:
        audio = elevenlabs.text_to_speech.convert(
            text=text,
            voice_id=VOICE_ID,
            model_id="eleven_monolingual_v1",
            output_format="mp3_44100_128"
        )
        play(audio)
    except Exception as e:
        print(f"Error from ElevenLabs: {e}")
        traceback.print_exc()
        raise RuntimeError("Failed to generate or play speech audio.")
