FROM python:3.12-slim

# Install system dependencies for Celery worker
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libraw-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libwebp-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install uv for package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml README.md ./
COPY backend/ ./backend/

# Install dependencies
RUN uv pip install --system -e .

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=config.settings

# Create app user with fixed UID (must match backend for volume sharing)
RUN groupadd -r -g 1000 app && useradd -r -u 1000 -g app app

# Create temp upload directory and celery data directory with correct permissions
RUN mkdir -p /tmp/photo_import_uploads /var/lib/celery && \
    chown -R app:app /tmp/photo_import_uploads /var/lib/celery /app

WORKDIR /app/backend

# Switch to app user
USER app

# Run Celery worker - consume high priority queue first, then default, then low
# This ensures photos are processed before videos
CMD ["celery", "-A", "config", "worker", "--loglevel=info", "--concurrency=2", "-Q", "high,default,low"]
