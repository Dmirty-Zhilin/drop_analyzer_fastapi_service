"""
Обновленный модуль analysis.py с асинхронной обработкой тяжелых задач и интеграцией улучшенного экспорта
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Depends
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import uuid
import asyncio
import logging

# Настройка логгера
logger = logging.getLogger(__name__)

from app.utils.export_utils import export_report
from app.utils.pagination import paginate, run_in_background, PaginatedResponse
from app.models.analysis.task_models import TaskCreate, TaskResponse, TaskDetailResponse

router = APIRouter()

# Временное хранилище задач (в реальном приложении должно быть заменено на базу данных)
fake_tasks_db = {}

@router.get("/", response_model=PaginatedResponse[TaskResponse])
async def list_tasks(
    page: int = Query(1, ge=1, description="Номер страницы"),
    page_size: int = Query(20, ge=1, le=100, description="Количество элементов на странице")
):
    """
    Получить пагинированный список всех задач анализа.
    """
    tasks_list = [
        TaskResponse(
            id=task_id,
            task_name=task_data["task_name"],
            status=task_data["status"],
            created_at=task_data["created_at"],
            domains_count=len(task_data["domains"])
        )
        for task_id, task_data in fake_tasks_db.items()
    ]
    
    # Применяем пагинацию
    return await paginate(tasks_list, page, page_size)

@router.post("/analyze", response_model=TaskResponse)
async def analyze_domains(
    task_data: TaskCreate,
    background_tasks: BackgroundTasks
):
    """
    Создать новую задачу анализа доменов.
    Анализ будет выполнен асинхронно в фоновом режиме.
    """
    task_id = str(uuid.uuid4())
    created_at = datetime.utcnow()
    
    # Создаем новую задачу
    task = {
        "id": task_id,
        "task_name": task_data.task_name,
        "domains": task_data.domains,
        "status": "pending",
        "created_at": created_at,
        "completed_at": None,
        "results": []
    }
    
    # Сохраняем задачу в базу данных
    fake_tasks_db[task_id] = task
    
    # Запускаем анализ в фоновом режиме
    run_in_background(background_tasks, process_analysis_task, task_id, task_data.domains)
    
    return TaskResponse(
        id=task_id,
        task_name=task_data.task_name,
        status="pending",
        created_at=created_at,
        domains_count=len(task_data.domains)
    )

# Добавляем алиасы для совместимости с фронтендом
# ВАЖНО: Алиасы должны быть объявлены ДО параметрического маршрута /{task_id}

@router.get("/tasks/{task_id}", response_model=TaskDetailResponse)
async def get_task_alias(task_id: str):
    """
    Алиас для получения детальной информации о задаче анализа по ID.
    Обеспечивает совместимость с фронтендом, который может использовать этот путь.
    """
    if task_id not in fake_tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_data = fake_tasks_db[task_id]
    
    return TaskDetailResponse(
        id=task_id,
        task_name=task_data["task_name"],
        status=task_data["status"],
        created_at=task_data["created_at"],
        completed_at=task_data["completed_at"],
        domains_count=len(task_data["domains"]),
        domains=task_data["domains"],
        results=task_data["results"]
    )

@router.get("/status/{task_id}", response_model=TaskDetailResponse)
async def get_task_status_alias(task_id: str):
    """
    Алиас для получения статуса задачи анализа по ID.
    Обеспечивает совместимость с фронтендом, который может использовать этот путь.
    """
    if task_id not in fake_tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_data = fake_tasks_db[task_id]
    
    return TaskDetailResponse(
        id=task_id,
        task_name=task_data["task_name"],
        status=task_data["status"],
        created_at=task_data["created_at"],
        completed_at=task_data["completed_at"],
        domains_count=len(task_data["domains"]),
        domains=task_data["domains"],
        results=task_data["results"]
    )

# Основной маршрут для получения задачи по ID
@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task(task_id: str):
    """
    Получить детальную информацию о задаче анализа по ID.
    """
    if task_id not in fake_tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_data = fake_tasks_db[task_id]
    
    return TaskDetailResponse(
        id=task_id,
        task_name=task_data["task_name"],
        status=task_data["status"],
        created_at=task_data["created_at"],
        completed_at=task_data["completed_at"],
        domains_count=len(task_data["domains"]),
        domains=task_data["domains"],
        results=task_data["results"]
    )

# Алиас, который должен быть после основного маршрута /{task_id}
@router.get("/{task_id}/status", response_model=TaskDetailResponse)
async def get_task_status_alias2(task_id: str):
    """
    Еще один алиас для получения статуса задачи анализа по ID.
    Обеспечивает совместимость с фронтендом, который может использовать этот путь.
    """
    if task_id not in fake_tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_data = fake_tasks_db[task_id]
    
    return TaskDetailResponse(
        id=task_id,
        task_name=task_data["task_name"],
        status=task_data["status"],
        created_at=task_data["created_at"],
        completed_at=task_data["completed_at"],
        domains_count=len(task_data["domains"]),
        domains=task_data["domains"],
        results=task_data["results"]
    )

@router.get("/export/{report_id}")
async def export_analysis_report(
    report_id: str,
    format: str = Query("excel", description="Формат экспорта (excel, csv, pdf)"),
    filter_type: Optional[str] = Query(None, description="Тип фильтра (long-live)"),
    background_tasks: BackgroundTasks = None
):
    """
    Экспортировать отчет в выбранном формате.
    Использует улучшенную функцию экспорта с обработкой ошибок и временных файлов.
    """
    return await export_report(report_id, format, filter_type, background_tasks)

@router.get("/majestic/{domain}")
async def get_majestic_data(domain: str):
    """
    Получить данные Majestic для указанного домена.
    В реальном приложении здесь должен быть запрос к API Majestic.
    """
    # Имитация запроса к API Majestic
    # В реальном приложении здесь должен быть настоящий запрос к API
    await asyncio.sleep(1)  # Имитация задержки сети
    
    # Возвращаем тестовые данные
    return {
        "domain": domain,
        "majestic_data": {
            "domain_authority": round(0.1 + 0.8 * hash(domain) % 100 / 100, 1),  # Случайное значение от 0.1 до 0.9
            "page_authority": round(0.1 + 0.8 * (hash(domain) + 1) % 100 / 100, 1),  # Случайное значение от 0.1 до 0.9
            "trust_flow": int(10 + 80 * hash(domain) % 100 / 100),  # Случайное значение от 10 до 90
            "citation_flow": int(10 + 80 * (hash(domain) + 2) % 100 / 100),  # Случайное значение от 10 до 90
            "backlinks": int(100 + 9900 * hash(domain) % 100 / 100),  # Случайное значение от 100 до 10000
            "referring_domains": int(10 + 990 * hash(domain) % 100 / 100),  # Случайное значение от 10 до 1000
        }
    }

async def process_analysis_task(task_id: str, domains: List[str]):
    """
    Асинхронная функция для обработки задачи анализа доменов.
    Использует реальный анализ через Wayback Machine API.
    """
    # Импортируем модуль анализа
    from app.utils.wayback_analyzer import analyze_domains
    
    # Обновляем статус задачи
    if task_id in fake_tasks_db:
        fake_tasks_db[task_id]["status"] = "processing"
    
    try:
        # Выполняем реальный анализ доменов через Wayback Machine API
        results = await analyze_domains(domains, concurrency=5)
        
        # Проверяем результаты
        if not results:
            logger.warning(f"No results returned from domain analysis for task {task_id}")
            # Обновляем задачу с ошибкой
            if task_id in fake_tasks_db:
                fake_tasks_db[task_id]["status"] = "failed"
                fake_tasks_db[task_id]["error"] = "No results returned from domain analysis"
            return
            
        logger.info(f"Successfully analyzed {len(results)} domains for task {task_id}")
    except Exception as e:
        logger.error(f"Error during domain analysis for task {task_id}: {e}")
        # Обновляем задачу с ошибкой
        if task_id in fake_tasks_db:
            fake_tasks_db[task_id]["status"] = "failed"
            fake_tasks_db[task_id]["error"] = str(e)
        return
    
    # Обновляем задачу с результатами
    if task_id in fake_tasks_db:
        fake_tasks_db[task_id]["status"] = "completed"
        fake_tasks_db[task_id]["completed_at"] = datetime.utcnow()
        fake_tasks_db[task_id]["results"] = results
