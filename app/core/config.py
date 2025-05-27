"""
Конфигурационный модуль для FastAPI приложения
"""
import os
from typing import List, Optional
from pydantic import BaseSettings

class Settings(BaseSettings):
    """
    Настройки приложения, загружаемые из переменных окружения
    """
    # Основные настройки API
    API_PORT: int = int(os.getenv("API_PORT", 8012))
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
    
    # CORS настройки
    ALLOWED_ORIGINS: List[str] = [
        "https://qo8k8k0c48sk080ccwgswocg.alettidesign.ru",
        "http://qo8k8k0c48sk080ccwgswocg.alettidesign.ru",
        "http://45.155.207.218:3090",
        "https://45.155.207.218:3090",
        "http://localhost:3090",
    ]
    
    # Настройки для внешних API
    OPENROUTER_API_KEY: Optional[str] = os.getenv("OPENROUTER_API_KEY")
    
    # Настройки Redis для Celery
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB: int = int(os.getenv("REDIS_DB", 0))
    
    # Настройки для временных файлов
    TEMP_DIR: str = os.getenv("TEMP_DIR", "/tmp/drop_analyzer")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Создаем экземпляр настроек
settings = Settings()
