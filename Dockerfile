FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libjpeg-dev \
    libpng-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libopenjp2-7-dev \
    libtiff5-dev \
    libwebp-dev \
    libharfbuzz-dev \
    libfribidi-dev \
    libxcb1-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p uploads logs cache exports static templates

# Set permissions
RUN chmod +x app_enterprise.py

# Create non-root user
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "app_enterprise:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# Alternative commands for different deployment scenarios
# Development: uvicorn app_enterprise:app --host 0.0.0.0 --port 8000 --reload
# Production with Gunicorn: gunicorn app_enterprise:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
# Celery Worker: celery -A app_enterprise.celery_app worker --loglevel=info --concurrency=4
# Celery Beat: celery -A app_enterprise.celery_app beat --loglevel=info
