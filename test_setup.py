#!/usr/bin/env python3
"""
Quick test script to verify all dependencies are working
"""

def test_imports():
    """Test if all required libraries can be imported"""
    try:
        import streamlit as st
        print("✅ Streamlit imported successfully")
    except ImportError as e:
        print(f"❌ Streamlit import failed: {e}")
    
    try:
        import elevenlabs
        print("✅ ElevenLabs imported successfully")
    except ImportError as e:
        print(f"❌ ElevenLabs import failed: {e}")
    
    try:
        from google.cloud import vision
        print("✅ Google Cloud Vision imported successfully")
    except ImportError as e:
        print(f"❌ Google Cloud Vision import failed: {e}")
    
    try:
        from google.cloud import speech
        print("✅ Google Cloud Speech imported successfully")
    except ImportError as e:
        print(f"❌ Google Cloud Speech import failed: {e}")
    
    try:
        import google.generativeai as genai
        print("✅ Google Generative AI imported successfully")
    except ImportError as e:
        print(f"❌ Google Generative AI import failed: {e}")
    
    try:
        from docx import Document
        print("✅ python-docx imported successfully")
    except ImportError as e:
        print(f"❌ python-docx import failed: {e}")
    
    try:
        from PIL import Image
        print("✅ Pillow imported successfully")
    except ImportError as e:
        print(f"❌ Pillow import failed: {e}")
    
    try:
        import cv2
        print("✅ OpenCV imported successfully")
    except ImportError as e:
        print(f"❌ OpenCV import failed: {e}")
    
    try:
        import numpy as np
        print("✅ NumPy imported successfully")
    except ImportError as e:
        print(f"❌ NumPy import failed: {e}")

def test_environment():
    """Test environment variables"""
    import os
    
    env_vars = ['ELEVENLABS_API_KEY', 'GEMINI_API_KEY']
    
    for var in env_vars:
        if os.getenv(var):
            print(f"✅ {var} is set")
        else:
            print(f"⚠️ {var} is not set")
    
    if os.path.exists('service_account.json'):
        print("✅ service_account.json found")
    else:
        print("⚠️ service_account.json not found")

if __name__ == "__main__":
    print("🔍 Testing Document Voice Filler Dependencies\n")
    
    print("📦 Testing imports...")
    test_imports()
    
    print("\n🔧 Testing environment...")
    test_environment()
    
    print("\n✨ Test completed!")
    print("\nTo run the application:")
    print("streamlit run app.py")
