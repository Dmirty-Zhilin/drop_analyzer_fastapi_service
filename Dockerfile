# Берём официальный образ с Python 3.11 (версии slim)
FROM python:3.11-slim

# Отключаем запись pyc-файлов и буферизацию вывода
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Задаём рабочую директорию внутри контейнера
WORKDIR /app

# Устанавливаем все системные библиотеки, которые нужны для WeasyPrint
# (Cairo, Pango, GObject, GDK-Pixbuf и т.д.), а также базовые инструменты сборки.
RUN apt-get update && apt-get install -y --no-install-recommends \
    # 1) Библиотеки для рендеринга WeasyPrint (Cairo, Pango, GObject):
    libgobject-2.0-0 \
    libglib2.0-0 \
    libcairo2 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libharfbuzz0b \
    libharfbuzz-subset0 \
    # 2) Для работы с растровыми изображениями (JPEG/PNG):
    libgdk-pixbuf2.0-0 \
    libjpeg-dev \
    # 3) Для работы с системными шрифтами:
    libfontconfig1 \
    # 4) Для сборки CFFI-модулей (cryptography, CFFI и т.п.):
    libffi-dev \
    # 5) Если в requirements.txt есть psycopg2, раскомментируйте эту строку:
    # libpq-dev \
    # 6) Базовые инструменты сборки (gcc, python3-dev и т.д.):
    build-essential \
    python3-dev \
 && rm -rf /var/lib/apt/lists/*

# Копируем только файл с зависимостями, чтобы кэшировать слой Docker
COPY requirements.txt /app/requirements.txt

# Обновляем pip и устанавливаем Python-библиотеки
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /app/requirements.txt

# Копируем весь код приложения
COPY ./app /app/app

# Открываем порт 8000 (он же объявлен в вашем Uvicorn)
EXPOSE 8000

# Запускаем FastAPI-приложение через Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
