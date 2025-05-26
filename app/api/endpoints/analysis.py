"""
Обновленный модуль analysis.py с асинхронной обработкой тяжелых задач и интеграцией улучшенного экспорта
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Depends
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import uuid
import asyncio

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
    В реальном приложении здесь должна быть логика анализа доменов.
    """
    # Обновляем статус задачи
    if task_id in fake_tasks_db:
        fake_tasks_db[task_id]["status"] = "processing"
    
    # Имитация длительной обработки
    await asyncio.sleep(2)
    
    # Генерация уникальных результатов анализа для каждого домена
    results = []
    for domain in domains:
        # Используем хеш домена для генерации уникальных значений
        domain_hash = hash(domain)
        
        # Генерируем уникальные данные на основе хеша домена
        total_snapshots = 50 + abs(domain_hash % 200)
        first_year = 2005 + abs(domain_hash % 10)
        last_year = 2020 + abs((domain_hash // 10) % 5)
        years_covered = last_year - first_year
        avg_interval = round(20 + abs(domain_hash % 60), 1)
        max_gap = 60 + abs(domain_hash % 100)
        timemap_count = 3 + abs(domain_hash % 10)
        score = round(5.0 + (abs(domain_hash % 50) / 10), 1)
        
        # Формируем результат с уникальными значениями
        result = {
            "domain_name": domain,
            "has_snapshot": True,
            "total_snapshots": total_snapshots,
            "first_snapshot": f"{first_year}-01-01",
            "last_snapshot": f"{last_year}-01-01",
            "years_covered": years_covered,
            "avg_interval_days": avg_interval,
            "max_gap_days": max_gap,
            "timemap_count": timemap_count,
            "recommended": score > 7.0,
            "assessment_score": score,
            "assessment_summary": f"Домен {domain} имеет {'хорошую' if score > 7.0 else 'среднюю'} историю в архиве."
        }
        results.append(result)
    
    # Обновляем задачу с результатами
    if task_id in fake_tasks_db:
        fake_tasks_db[task_id]["status"] = "completed"
        fake_tasks_db[task_id]["completed_at"] = datetime.utcnow()
        fake_tasks_db[task_id]["results"] = results
