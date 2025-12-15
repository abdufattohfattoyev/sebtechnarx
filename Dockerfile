FROM python:3.11-slim

# ✅ Fontlar va boshqa paketlar
RUN apt-get update && apt-get install -y \
    fonts-dejavu \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Data papkasini yaratish
RUN mkdir -p /app/data && chmod -R 777 /app/data

COPY requirements.txt .

# ✅ Pip upgrade va install
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

# ✅ Environment variables
ENV PYTHONUNBUFFERED=1
ENV MALLOC_ARENA_MAX=2

CMD ["python", "app.py"]