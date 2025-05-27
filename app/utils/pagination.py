"""
Модуль для пагинации и асинхронной обработки запросов
"""
from typing import TypeVar, Generic, List, Optional, Callable, Any
from pydantic import BaseModel, Field
from fastapi import Query, BackgroundTasks

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    """
    Модель для пагинированного ответа API
    """
    items: List[T]
    total: int
    page: int
    pages: int
    has_next: bool
    has_prev: bool

async def paginate(
    items: List[Any],
    page: int = Query(1, ge=1, description="Номер страницы"),
    page_size: int = Query(20, ge=1, le=100, description="Количество элементов на странице")
) -> PaginatedResponse:
    """
    Функция для пагинации списка элементов
    
    Args:
        items: Список элементов для пагинации
        page: Номер страницы (начиная с 1)
        page_size: Количество элементов на странице
        
    Returns:
        PaginatedResponse: Пагинированный ответ
    """
    total = len(items)
    pages = (total + page_size - 1) // page_size if total > 0 else 1
    
    # Проверка валидности номера страницы
    if page > pages and total > 0:
        page = pages
    
    # Вычисление начального и конечного индексов
    start = (page - 1) * page_size
    end = min(start + page_size, total)
    
    # Получение элементов для текущей страницы
    paginated_items = items[start:end] if total > 0 else []
    
    return PaginatedResponse(
        items=paginated_items,
        total=total,
        page=page,
        pages=pages,
        has_next=page < pages,
        has_prev=page > 1
    )

def run_in_background(background_tasks: BackgroundTasks, func: Callable, *args, **kwargs) -> None:
    """
    Запускает функцию в фоновом режиме
    
    Args:
        background_tasks: Объект BackgroundTasks из FastAPI
        func: Функция для выполнения в фоновом режиме
        *args: Позиционные аргументы для функции
        **kwargs: Именованные аргументы для функции
    """
    background_tasks.add_task(func, *args, **kwargs)
