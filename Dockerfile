# Dockerfile - TO'LIQ SOZLANGAN
FROM python:3.11-slim

# Metadata
LABEL maintainer="abdufattoh.com"
LABEL description="Telegram Phone Pricing Bot"

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    postgresql-client \
    libpq-dev \
    fonts-dejavu \
    fonts-liberation \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Working directory
WORKDIR /app

# Create directories
RUN mkdir -p /app/data /app/temp /app/logs && \
    chmod -R 777 /app/data /app/temp /app/logs

# Copy requirements first (for caching)
COPY requirements.txt .

# Install Python packages
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV MALLOC_ARENA_MAX=2

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Run bot
CMD ["python", "app.py"]