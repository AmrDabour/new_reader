import os
from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path

# Azure OpenAI settings
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1")

# ElevenLabs settings
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_ENGLISH_VOICE_ID = os.getenv("ELEVENLABS_ENGLISH_VOICE_ID", "1SM7GgM6IMuvQlz2BwM3")
ELEVENLABS_ARABIC_VOICE_ID = os.getenv("ELEVENLABS_ARABIC_VOICE_ID", "1qEiC6qsybMkmnNdVMbK")

# Paths configuration
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Tesseract path - use environment variable or default based on OS
TESSERACT_CMD = os.getenv(
    "TESSERACT_CMD",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe" if os.name == "nt" else "/usr/bin/tesseract"
)

# YOLO model paths - في البيئة المحلية والإنتاج، الموديلات موجودة في مجلد models
MODELS_DIR = os.path.join(BASE_DIR, "models")
BOXES_MODEL_PATH = os.path.join(MODELS_DIR, "boxes.pt")
DOT_LINE_MODEL_PATH = os.path.join(MODELS_DIR, "dot_line.pt")

class Settings(BaseSettings):
    # Azure OpenAI Settings
    azure_openai_api_key: str
    azure_openai_endpoint: str
    azure_openai_api_version: str
    azure_openai_deployment_name: str

    # ElevenLabs Settings
    elevenlabs_api_key: str
    elevenlabs_english_voice_id: str
    elevenlabs_arabic_voice_id: str

    # YOLO Model Paths
    boxes_model_path: str = "boxes.pt"
    dot_line_model_path: str = "dot_line.pt"

    # Tesseract Configuration
    tesseract_cmd: str = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings():
    return Settings()

# Arabic Number Mapping
ARABIC_NUMBER_MAP = {
    'صفر': '0', 'زيرو': '0',
    'واحد': '1',
    'اثنين': '2', 'اثنان': '2',
    'ثلاثة': '3', 'ثلاثه': '3',
    'أربعة': '4', 'اربعه': '4',
    'خمسة': '5', 'خمسه': '5',
    'ستة': '6', 'سته': '6',
    'سبعة': '7', 'سبعه': '7',
    'ثمانية': '8', 'ثمانيه': '8',
    'تسعة': '9', 'تسعه': '9',
    'عشرة': '10', 'عشره': '10'
} 