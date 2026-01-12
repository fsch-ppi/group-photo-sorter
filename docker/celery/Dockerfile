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

# Create non-root user for security
RUN groupadd -r celery && useradd -r -g celery celery

# Create temp upload directory and celery data directory with correct permissions
RUN mkdir -p /tmp/photo_import_uploads /var/lib/celery && \
    chown -R celery:celery /tmp/photo_import_uploads /var/lib/celery

WORKDIR /app/backend

# Switch to non-root user
USER celery

# Run Celery worker
CMD ["celery", "-A", "config", "worker", "--loglevel=info", "--concurrency=2"]
