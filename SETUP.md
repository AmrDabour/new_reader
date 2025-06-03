# 🚀 Quick Setup Guide

## Prerequisites
- Python 3.8+
- Git
- Microphone access

## Step 1: Clone Repository
```bash
git clone https://github.com/mohamed-alawy/document-voice-filler.git
cd document-voice-filler
```

## Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

## Step 3: Get API Keys

### ElevenLabs API (Text-to-Speech)
1. Go to [elevenlabs.io](https://elevenlabs.io)
2. Sign up/Login
3. Get API key from dashboard

### Google Gemini API (Document Analysis)
1. Go to [Google AI Studio](https://makersuite.google.com)
2. Create API key

### Google Cloud APIs (Vision & Speech)
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create new project
3. Enable Vision API and Speech-to-Text API
4. Create service account
5. Download `service_account.json`

## Step 4: Setup Environment
1. Copy `.env.example` to `.env`
2. Add your API keys:
   ```
   ELEVENLABS_API_KEY=your_key_here
   GEMINI_API_KEY=your_key_here
   ```
3. Place `service_account.json` in project root

## Step 5: Test Setup
```bash
python test_setup.py
```

## Step 6: Run Application
```bash
streamlit run app.py
```

## 🎉 You're Ready!
Open your browser to the Streamlit URL and start filling forms with your voice!

## 🆘 Need Help?
- Check [README.md](README.md) for detailed documentation
- Run `python test_setup.py` to diagnose issues
- Open an issue on GitHub if you're stuck
