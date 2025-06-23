FROM python:3.11.7-slim

# Set working directory
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

# Upgrade pip and install essential Python build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy requirements first to use Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Set environment variables
ENV PORT=8000
ENV TESSERACT_CMD=/usr/bin/tesseract

# Expose the port (optional but good practice)
EXPOSE $PORT

# Run the FastAPI app with Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
