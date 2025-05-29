"""
Улучшенная версия main.py с исправленными CORS настройками для решения проблемы NetworkError
"""
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.endpoints import analysis, reports
from app.utils.error_handlers import ResourceNotFoundError, NetworkError, ServerError

# Создаем приложение FastAPI
app = FastAPI(title="Drop Domain Analyzer API", version="0.1.0")

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://qo8k8k0c48sk080ccwgswocg.alettidesign.ru"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Глобальный обработчик исключений
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Глобальный обработчик исключений для предоставления более информативных сообщений об ошибках
    """
    if isinstance(exc, ResourceNotFoundError):
        return JSONResponse(
            status_code=404,
            content={
                "detail": str(exc),
                "type": "ResourceNotFoundError"
            }
        )
    elif isinstance(exc, NetworkError):
        return JSONResponse(
            status_code=503,
            content={
                "detail": str(exc),
                "type": "NetworkError"
            }
        )
    elif isinstance(exc, ServerError):
        return JSONResponse(
            status_code=500,
            content={
                "detail": str(exc),
                "type": "ServerError"
            }
        )
    elif isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "type": "HTTPException"
            }
        )
    else:
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
