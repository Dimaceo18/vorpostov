FROM python:3.10-slim

WORKDIR /app

# Установка ffmpeg для обработки видео
RUN apt-get update && apt-get install -y \
    gcc \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Копирование и установка Python-зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода бота (БЕЗ .env!)
COPY bot.py .

# Создание пользователя для запуска
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

# Запуск бота
CMD ["python", "-u", "bot.py"]
