FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies (six dulu untuk pygrowup)
RUN pip install --no-cache-dir six && \
    pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p uploads logs cache exports static templates && \
    chmod +x app_enterprise.py

# Create non-root user
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

EXPOSE 8000

# **1 worker untuk hemat memory 512MiB**
CMD ["uvicorn", "app_enterprise:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--loop", "uvloop", "--http", "httptools"]
