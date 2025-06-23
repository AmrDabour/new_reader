FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including Tesseract
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    tesseract-ocr \
    tesseract-ocr-ara \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application (including models)
COPY . .

# Use PORT environment variable with fallback to 8000
ENV PORT=8000
ENV TESSERACT_CMD=/usr/bin/tesseract

# Command to run the application
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT 