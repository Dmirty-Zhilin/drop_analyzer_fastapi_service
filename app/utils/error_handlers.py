"""
Утилиты для обработки ошибок и механизма повторных попыток
"""
import logging
import asyncio
from typing import Any, Callable, TypeVar, Optional
from fastapi import HTTPException
from aiohttp import ClientResponse, ClientError

# Настройка логгера
logger = logging.getLogger(__name__)

T = TypeVar('T')

class RetryableError(Exception):
    """Базовый класс для ошибок, которые можно повторить"""
    pass

class NetworkError(RetryableError):
    """Ошибка сети"""
    pass

class ServerError(RetryableError):
    """Ошибка сервера"""
    pass

class ResourceNotFoundError(Exception):
    """Ресурс не найден"""
    pass

async def retry_async(
    func: Callable[..., T],
    *args: Any,
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (RetryableError,),
    **kwargs: Any
) -> T:
    """
    Асинхронная функция для повторных попыток выполнения операции
    
    Args:
        func: Асинхронная функция для выполнения
        *args: Позиционные аргументы для функции
        max_retries: Максимальное количество попыток
        delay: Начальная задержка между попытками в секундах
        backoff_factor: Множитель для увеличения задержки
        exceptions: Кортеж исключений, при которых нужно повторять попытку
        **kwargs: Именованные аргументы для функции
    
    Returns:
        Результат выполнения функции
    
    Raises:
        Exception: Последнее исключение после всех попыток
    """
    last_exception = None
    current_delay = delay

    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            if attempt < max_retries:
                logger.warning(
                    f"Попытка {attempt + 1} из {max_retries + 1} не удалась: {str(e)}. "
                    f"Повторная попытка через {current_delay} секунд..."
                )
                await asyncio.sleep(current_delay)
                current_delay *= backoff_factor
            else:
                logger.error(f"Все попытки исчерпаны. Последняя ошибка: {str(e)}")
                raise last_exception

def handle_http_error(response: ClientResponse) -> None:
    """
    Обработка HTTP ошибок
    
    Args:
        response: Объект ответа aiohttp
    
    Raises:
        ResourceNotFoundError: Если ресурс не найден (404)
        ServerError: Если ошибка сервера (500)
        HTTPException: Для других HTTP ошибок
    """
    if response.status == 404:
        raise ResourceNotFoundError("Ресурс не найден")
    elif response.status >= 500:
        raise ServerError(f"Ошибка сервера: {response.status}")
    else:
        raise HTTPException(
            status_code=response.status,
            detail=f"HTTP ошибка! Статус: {response.status}"
        )

async def safe_request(
    session,
    method: str,
    url: str,
    **kwargs
) -> Any:
    """
    Безопасный запрос с обработкой ошибок
    
    Args:
        session: Сессия aiohttp
        method: HTTP метод
        url: URL для запроса
        **kwargs: Дополнительные параметры запроса
    
    Returns:
        Результат запроса
    
    Raises:
        NetworkError: При ошибках сети
        ResourceNotFoundError: При 404
        ServerError: При 500+
        HTTPException: При других HTTP ошибках
    """
    try:
        async with session.request(method, url, **kwargs) as response:
            if not response.ok:
                handle_http_error(response)
            return await response.json()
    except ClientError as e:
        raise NetworkError(f"Ошибка сети: {str(e)}")
    except asyncio.TimeoutError:
        raise NetworkError("Превышено время ожидания запроса") 