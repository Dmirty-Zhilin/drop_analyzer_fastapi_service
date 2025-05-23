# Базовый образ с Python 3.11 (облегчённый вариант)
FROM python:3.11-slim

# Отключаем запись pyc-файлов и буферизацию вывода Python
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Задаём рабочую директорию внутри контейнера
WORKDIR /app

# Устанавливаем все необходимые системные зависимости для WeasyPrint
# и прочих «нативных» пакетов (Cairo, Pango, GObject, GDK-Pixbuf и т.д.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # 1) Библиотеки для рендеринга WeasyPrint (Pango/Cairo/GObject)
    libpango-1.0-0 \
    libharfbuzz0b \
    libpangoft2-1.0-0 \
    libgobject-2.0-0 \
    libcairo2 \
    libpangocairo-1.0-0 \
    # 2) Для обработки растровых изображений (JPEG/PNG)
    libgdk-pixbuf2.0-0 \
    libjpeg-dev \
    # 3) Для работы с системными шрифтами
    libfontconfig1 \
    # 4) Для сборки CFFI-модулей (cryptography, WeasyPrint использует CFFI)
    libffi-dev \
    # 5) Если в requirements.txt упоминается psycopg2, раскомментируйте строку:
    # libpq-dev \
    # 6) Дополнительные инструменты сборки (make, gcc и т.д.)  
    build-essential \
    python3-dev \
 && rm -rf /var/lib/apt/lists/*

# Копируем только файл с зависимостями, чтобы кэшировать слой Docker
COPY requirements.txt /app/requirements.txt

# Обновляем pip и устанавливаем Python-зависимости
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /app/requirements.txt

# Копируем весь код приложения в контейнер
COPY ./app /app/app

# Открываем порт, на котором будет работать Uvicorn
EXPOSE 8000

# Запускаем FastAPI через Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
