"""
Обновленный модуль analysis.py с асинхронной обработкой тяжелых задач, 
оптимизацией скорости и отслеживанием прогресса в реальном времени
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Depends
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
import uuid
import asyncio
import logging
import time
import aiohttp
from concurrent.futures import ThreadPoolExecutor

# Настройка логгера
logger = logging.getLogger(__name__)

from app.utils.export_utils import export_report
from app.utils.pagination import paginate, run_in_background, PaginatedResponse
from app.models.analysis.task_models import TaskCreate, TaskResponse, TaskDetailResponse

router = APIRouter()

# Временное хранилище задач (в реальном приложении должно быть заменено на базу данных)
fake_tasks_db = {}

# Пул потоков для параллельной обработки
thread_pool = ThreadPoolExecutor(max_workers=10)

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
            domains_count=len(task_data["domains"]),
            progress=task_data.get("progress", 0),
            current_domain=task_data.get("current_domain", None)
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
        "results": [],
        "progress": 0,
        "current_domain": None,
        "use_test_data": task_data.use_test_data
    }
    
    # Сохраняем задачу в базу данных
    fake_tasks_db[task_id] = task
    
    # Запускаем анализ в фоновом режиме
    run_in_background(background_tasks, process_analysis_task, task_id, task_data.domains, task_data.use_test_data)
    
    return TaskResponse(
        id=task_id,
        task_name=task_data.task_name,
        status="pending",
        created_at=created_at,
        domains_count=len(task_data.domains),
        progress=0,
        current_domain=None
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
        completed_at=task_data.get("completed_at"),
        domains_count=len(task_data["domains"]),
        domains=task_data["domains"],
        results=task_data["results"],
        progress=task_data.get("progress", 0),
        current_domain=task_data.get("current_domain"),
        error=task_data.get("error")
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
        completed_at=task_data.get("completed_at"),
        domains_count=len(task_data["domains"]),
        domains=task_data["domains"],
        results=task_data["results"],
        progress=task_data.get("progress", 0),
        current_domain=task_data.get("current_domain"),
        error=task_data.get("error")
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
        completed_at=task_data.get("completed_at"),
        domains_count=len(task_data["domains"]),
        domains=task_data["domains"],
        results=task_data["results"],
        progress=task_data.get("progress", 0),
        current_domain=task_data.get("current_domain"),
        error=task_data.get("error")
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
        completed_at=task_data.get("completed_at"),
        domains_count=len(task_data["domains"]),
        domains=task_data["domains"],
        results=task_data["results"],
        progress=task_data.get("progress", 0),
        current_domain=task_data.get("current_domain"),
        error=task_data.get("error")
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
    await asyncio.sleep(0.2)  # Уменьшена задержка для ускорения работы
    
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

# Функция для генерации тестовых данных
def generate_test_data(domain: str) -> Dict[str, Any]:
    """
    Генерирует тестовые данные для домена
    """
    domain_hash = hash(domain)
    return {
        "domain": domain,
        "domain_name": domain,
        "has_snapshot": bool(domain_hash % 2),
        "availability_ts": float(time.time() * 1e9) if domain_hash % 2 else None,
        "total_snapshots": int(200 + 1000 * (domain_hash % 100) / 100),
        "timemap_count": int(10 + 50 * (domain_hash % 100) / 100),
        "first_snapshot": datetime.now().replace(year=datetime.now().year - 5).isoformat(),
        "last_snapshot": datetime.now().isoformat(),
        "avg_interval_days": float(1 + 10 * (domain_hash % 100) / 100),
        "max_gap_days": float(30 + 300 * (domain_hash % 100) / 100),
        "years_covered": float(1 + 9 * (domain_hash % 100) / 100),
        "snapshots_per_year": {"2020": 100, "2021": 200, "2022": 300, "2023": 400, "2024": 500},
        "unique_versions": float(100 + 900 * (domain_hash % 100) / 100),
        "is_good": bool((domain_hash % 10) > 3),
        "is_long_live": bool((domain_hash % 10) > 7),
        "recommended": bool((domain_hash % 10) > 5),
        "analysis_time_sec": float(1 + 5 * (domain_hash % 100) / 100)
    }

async def process_analysis_task(task_id: str, domains: List[str], use_test_data: bool = False):
    """
    Асинхронная функция для обработки задачи анализа доменов.
    Использует реальный анализ через Wayback Machine API или тестовые данные.
    Отслеживает прогресс и обновляет статус задачи в реальном времени.
    """
    # Обновляем статус задачи
    if task_id in fake_tasks_db:
        fake_tasks_db[task_id]["status"] = "processing"
        fake_tasks_db[task_id]["progress"] = 0
        fake_tasks_db[task_id]["results"] = []
    
    total_domains = len(domains)
    results = []
    
    try:
        if use_test_data:
            # Используем тестовые данные для быстрой демонстрации
            for i, domain in enumerate(domains):
                # Обновляем прогресс и текущий домен
                if task_id in fake_tasks_db:
                    fake_tasks_db[task_id]["progress"] = (i / total_domains) * 100
                    fake_tasks_db[task_id]["current_domain"] = domain
                
                # Генерируем тестовые данные
                test_data = generate_test_data(domain)
                results.append(test_data)
                
                # Добавляем результат в задачу
                if task_id in fake_tasks_db:
                    fake_tasks_db[task_id]["results"].append(test_data)
                
                # Имитация времени обработки
                await asyncio.sleep(0.2)
        else:
            # Импортируем модуль анализа
            from app.utils.wayback_analyzer import analyze_domains, analyze_domain
            
            # Создаем сессию aiohttp для всех запросов
            async with aiohttp.ClientSession() as session:
                # Оптимизированный анализ с отслеживанием прогресса
                async def process_domain(domain, index):
                    try:
                        # Обновляем прогресс и текущий домен
                        if task_id in fake_tasks_db:
                            fake_tasks_db[task_id]["progress"] = (index / total_domains) * 100
                            fake_tasks_db[task_id]["current_domain"] = domain
                        
                        # Анализируем домен, передавая сессию
                        result = await analyze_domain(domain, session)
                        
                        # Добавляем результат в задачу
                        if task_id in fake_tasks_db and result:
                            fake_tasks_db[task_id]["results"].append(result)
                        
                        return result
                    except Exception as e:
                        logger.error(f"Error analyzing domain {domain}: {e}")
                        return None
                
                # Создаем задачи для всех доменов
                tasks = []
                for i, domain in enumerate(domains):
                    tasks.append(process_domain(domain, i))
                
                # Выполняем задачи с ограничением concurrency
                concurrency = 10  # Увеличено для ускорения
                for i in range(0, len(tasks), concurrency):
                    batch = tasks[i:i+concurrency]
                    batch_results = await asyncio.gather(*batch)
                    results.extend([r for r in batch_results if r])
        
        # Проверяем результаты
        if not results:
            logger.warning(f"No results returned from domain analysis for task {task_id}")
            # Обновляем задачу с ошибкой
            if task_id in fake_tasks_db:
                fake_tasks_db[task_id]["status"] = "failed"
                fake_tasks_db[task_id]["error"] = "No results returned from domain analysis"
                fake_tasks_db[task_id]["progress"] = 0
            return
            
        logger.info(f"Successfully analyzed {len(results)} domains for task {task_id}")
    except Exception as e:
        logger.error(f"Error during domain analysis for task {task_id}: {e}")
        # Обновляем задачу с ошибкой
        if task_id in fake_tasks_db:
            fake_tasks_db[task_id]["status"] = "failed"
            fake_tasks_db[task_id]["error"] = str(e)
            fake_tasks_db[task_id]["progress"] = 0
        return
    
    # Обновляем задачу с результатами
    if task_id in fake_tasks_db:
        fake_tasks_db[task_id]["status"] = "completed"
        fake_tasks_db[task_id]["completed_at"] = datetime.utcnow()
        fake_tasks_db[task_id]["results"] = results
        fake_tasks_db[task_id]["progress"] = 100
        fake_tasks_db[task_id]["current_domain"] = None
