# Drop Analyzer Backend

Бэкенд-сервис для анализа доменов и генерации отчетов о дропах.

## Системные требования

### Python зависимости
Все необходимые Python-зависимости указаны в файле `requirements.txt`. Установите их с помощью:

```bash
pip install -r requirements.txt
```

### Системные зависимости
Для корректной работы WeasyPrint (библиотека для генерации PDF) необходимо установить следующие системные зависимости:

#### Ubuntu/Debian
```bash
apt-get update && apt-get install -y libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0 libgobject-2.0-0 libcairo2 libpangocairo-1.0-0
```

#### CentOS/RHEL
```bash
yum install -y pango harfbuzz libpangoft2 gobject-introspection cairo pangocairo
```

#### Alpine Linux
```bash
apk add --no-cache pango harfbuzz glib cairo
```

## Запуск сервиса

```bash
uvicorn app.main:app --reload --port 8012
```

## API документация

После запуска сервиса API документация доступна по адресу:
```
http://localhost:8012/docs
```

## Функциональность

- Анализ доменов через Wayback Machine
- Генерация отчетов о дропах
- Фильтрация дропов по различным параметрам
- Экспорт отчетов в форматах Excel, CSV и PDF
- Интеграция с OpenRouter API для тематического анализа
