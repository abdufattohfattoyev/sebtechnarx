FROM python:3.11-slim

# Fontlarni o'rnatish
RUN apt-get update && apt-get install -y \
    fonts-dejavu \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Data papkasini yaratish
RUN mkdir -p /app/data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Data papkasiga ruxsat berish
RUN chmod -R 777 /app/data

CMD ["python", "app.py"]