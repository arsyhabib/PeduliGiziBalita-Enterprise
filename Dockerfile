FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir six && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p uploads logs cache exports static templates && \
    chmod +x app_enterprise.py

# BUAT USER DAHULU SEBELUM CHOWN
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app

USER app

EXPOSE 8000

# **REDUCE WORKERS FROM 4 TO 1** - Hemat memory 75%
CMD ["uvicorn", "app_enterprise:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--loop", "uvloop", "--http", "httptools"]
