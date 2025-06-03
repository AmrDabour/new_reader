import os
from elevenlabs.client import ElevenLabs

API_KEY = os.getenv("ELEVENLABS_API_KEY")
if not API_KEY:
    print("ELEVENLABS_API_KEY is not set.")
    exit(1)

elevenlabs = ElevenLabs(api_key=API_KEY)
voices = elevenlabs.voices.get_all()
for voice in voices.voices:
    print(f"Name: {voice.name}, ID: {voice.voice_id}")
