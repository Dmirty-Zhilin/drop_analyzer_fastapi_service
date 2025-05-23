FROM python:3.11-slim-bullseye

# Отключаем запись .pyc и буферизацию вывода Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Устанавливаем только «runtime»-зависимости для WeasyPrint (и побочно задействованных модулей),
# без несуществующих пакетов. После этого уже можно ставить weasyprint через pip.
RUN apt-get update && apt-get install -y --no-install-recommends \
    # 1) Базовая библиотека GLib (в ней содержится GObject):
    libglib2.0-0 \
    # 2) Cairo (движок 2D-графики) и модуль pangocairo:
    libcairo2 \
    libpangocairo-1.0-0 \
    # 3) Pango (рендеринг шрифтов) и HarfBuzz (шейпинг):
    libpango-1.0-0 \
    libharfbuzz0b \
    # 4) GDK-Pixbuf (чтобы WeasyPrint мог обрабатывать JPEG/PNG):
    libgdk-pixbuf2.0-0 \
    # 5) Fontconfig (поиск и конфиг системных шрифтов):
    libfontconfig1 \
    # 6) JPEG / OpenJPEG (если используется Pillow):
    libjpeg62-turbo \
    libopenjp2-7 \
    # 7) libffi (CFFI для WeasyPrint/cryptography и т.д.):
    libffi7 \
    # 8) (Опционально) libpq5 — если в requirements есть psycopg2-binary, оно подтянет libpq5 само.
    # Если же используется именно psycopg2 (не -binary), тогда нужен libpq-dev (но это -dev, нужен только при pip install, не для рантайма).
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements.txt и ставим Python-пакеты
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /app/requirements.txt

# Копируем весь код приложения
COPY ./app /app/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
