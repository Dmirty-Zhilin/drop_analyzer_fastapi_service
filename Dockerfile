# --------------------------------------------------------------------------------
# 1) Берём официальный образ Python 3.11 slim (Debian Bullseye)
# --------------------------------------------------------------------------------
FROM python:3.11-slim-bullseye

# --------------------------------------------------------------------------------
# 2) Отключаем запись .pyc и вывода stdout/stderr в буфер
# --------------------------------------------------------------------------------
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# --------------------------------------------------------------------------------
# 3) Устанавливаем рабочую директорию
# --------------------------------------------------------------------------------
WORKDIR /app

# --------------------------------------------------------------------------------
# 4) Устанавливаем «нативные» зависимости, нужные для WeasyPrint (и прочих C-зависимых пакетов):
#    – libgobject-2.0-0 / libglib2.0-0  (GObject/GLib)
#    – libcairo2 / libcairo2-dev         (Cairo 2D)
#    – libpango-1.0-0 / libpangoft2-1.0-0 / libpangocairo-1.0-0 (Pango)
#    – libharfbuzz0b / libharfbuzz-subset0 (HarfBuzz)
#    – libgdk-pixbuf2.0-0 / libgdk-pixbuf2.0-dev (GDK-Pixbuf для PNG/JPEG)
#    – libjpeg62-turbo-dev / libopenjp2-7-dev     (JPEG/OpenJPEG-заголовки)
#    – libfontconfig1                            (Fontconfig для шрифтов)
#    – libffi-dev / python3-dev / build-essential (для сборки CFFI, cryptography и т. д.)
#    (Если нужен psycopg2 → libpq-dev, раскомментируйте соответствующую строку ниже)
# --------------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    # GObject/GLib (libgobject-2.0.so.0 и зависимости)
    libgobject-2.0-0 \
    libglib2.0-0 \
    # Cairo 2D и заголовки
    libcairo2 \
    libcairo2-dev \
    # Pango (рендеринг шрифтов)
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    # HarfBuzz (шейпинг шрифтов)
    libharfbuzz0b \
    libharfbuzz-subset0 \
    # GDK-Pixbuf (PNG/JPEG)
    libgdk-pixbuf2.0-0 \
    libgdk-pixbuf2.0-dev \
    # JPEG / OpenJPEG
    libjpeg62-turbo-dev \
    libopenjp2-7-dev \
    # Fontconfig (поиск шрифтов)
    libfontconfig1 \
    # libffi-dev, python3-dev, build-essential (CFFI / сборка модулей)
    libffi-dev \
    python3-dev \
    build-essential \
    # libpq-dev  # <- раскомментируйте, если используете psycopg2
 && rm -rf /var/lib/apt/lists/*

# --------------------------------------------------------------------------------
# 5) Копируем только requirements.txt (чтобы слой pip install кэшировался)
# --------------------------------------------------------------------------------
COPY requirements.txt /app/requirements.txt

# --------------------------------------------------------------------------------
# 6) Устанавливаем Python-зависимости
# --------------------------------------------------------------------------------
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /app/requirements.txt

# --------------------------------------------------------------------------------
# 7) Копируем весь код приложения
# --------------------------------------------------------------------------------
COPY ./app /app/app

# --------------------------------------------------------------------------------
# 8) Открываем порт 8000 (тот же, который мы указываем в CMD ниже)
# --------------------------------------------------------------------------------
EXPOSE 8000

# --------------------------------------------------------------------------------
# 9) Запускаем FastAPI через Uvicorn
# --------------------------------------------------------------------------------
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
