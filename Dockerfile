# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
# We need ffmpeg for video processing and libav dev libraries for 'av' (PyAV)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    libavfilter-dev \
    pkg-config \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Create necessary directories
RUN mkdir -p uploads projects exports temp_output

# Expose port (default 8000, but will use $PORT env var)
EXPOSE 8000

# Run the application using uvicorn
# We use a shell command to ensure $PORT is expanded correctly
CMD sh -c "uvicorn api.server:app --host 0.0.0.0 --port ${PORT:-8000}"
