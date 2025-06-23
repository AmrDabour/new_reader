FROM python:3.11.7-slim

WORKDIR /app

# Install system dependencies including Tesseract
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    tesseract-ocr \
    tesseract-ocr-ara \
    tesseract-ocr-eng \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python packages with --no-deps to avoid dependency conflicts
RUN pip install --no-cache-dir pydantic-core>=2.14.0,<2.15.0 && \
    pip install --no-cache-dir -r requirements.txt

# Copy the application (including models)
COPY . .

# Use PORT environment variable with fallback to 8000
ENV PORT=8000
ENV TESSERACT_CMD=/usr/bin/tesseract

# Command to run the application
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT 