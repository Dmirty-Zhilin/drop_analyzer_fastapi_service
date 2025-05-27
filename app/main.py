"""
Улучшенная версия main.py с исправленными CORS настройками для решения проблемы NetworkError
"""
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.endpoints import analysis, reports

# Создаем приложение FastAPI
app = FastAPI(title="Drop Domain Analyzer API", version="0.1.0")

# Получаем список разрешенных доменов из переменной окружения или используем значения по умолчанию
default_origins = [
    "https://qo8k8k0c48sk080ccwgswocg.alettidesign.ru",  # Основной домен фронтенда
    "http://qo8k8k0c48sk080ccwgswocg.alettidesign.ru",   # HTTP версия домена фронтенда
    "http://45.155.207.218:3090",                        # Адрес фронтенда по IP и порту
    "https://45.155.207.218:3090",                       # HTTPS версия IP адреса
    "http://localhost:3090",                             # Локальный адрес для разработки
]

origins = os.getenv("ALLOWED_ORIGINS", ",".join(default_origins)).split(",")

# Добавляем CORS middleware с улучшенными настройками
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],                                 # Разрешаем все HTTP методы
    allow_headers=["*"],                                 # Разрешаем все заголовки
    expose_headers=["Content-Disposition", "Location"],  # Разрешаем доступ к заголовкам редиректа
    max_age=86400,                                       # Кэширование предзапросов на 24 часа
)

# Глобальный обработчик исключений
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Глобальный обработчик исключений для предоставления более информативных сообщений об ошибках
    """
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"Внутренняя ошибка сервера: {str(exc)}",
            "type": type(exc).__name__
        }
    )

@app.get("/", tags=["Root"])
async def read_root():
    """
    Корневой эндпоинт API
    """
    return {"message": "Welcome to Drop Domain Analyzer API"}

# Включаем роутеры с правильными путями (без trailing slash)
app.include_router(analysis.router, prefix="/api/v1/analysis", tags=["Analysis Tasks"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports"])

if __name__ == "__main__":
    import uvicorn
    # Получаем порт из переменной окружения или используем значение по умолчанию
    port = int(os.getenv("API_PORT", 8012))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
