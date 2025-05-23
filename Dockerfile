FROM python:3.11-slim-bullseye

# Установка переменных окружения
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Установка рабочей директории
WORKDIR /app

# Установка системных зависимостей для WeasyPrint
RUN apt-get update && apt-get install -y \
    build-essential \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libharfbuzz-subset0 \
    libgdk-pixbuf2.0-0 \
    libgdk-pixbuf2.0-dev \
    libcairo2 \
    libcairo2-dev \
    libgobject-2.0-0 \
    libgobject-2.0-dev \
    libffi-dev \
    libjpeg62-turbo-dev \
    libopenjp2-7-dev \
    python3-cffi \
    && rm -rf /var/lib/apt/lists/*

# Копирование и установка зависимостей Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копирование проекта
COPY ./app /app/app

# Открытие порта
EXPOSE 8000

# Запуск приложения
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
