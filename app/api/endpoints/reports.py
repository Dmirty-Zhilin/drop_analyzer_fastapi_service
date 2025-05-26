"""
Обновленный модуль reports.py с пагинацией и улучшенной обработкой ошибок
"""
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
import uuid
import json

from app.utils.pagination import paginate, PaginatedResponse
from app.models.reports.report_models import ReportCreate, ReportResponse, ReportDetailResponse

router = APIRouter()

# Временное хранилище отчетов (в реальном приложении должно быть заменено на базу данных)
fake_reports_db = {}

# Тестовые данные для демонстрации
def generate_test_data():
    if not fake_reports_db:
        report_id = "test-report-123"
        created_at = datetime.utcnow()
        
        # Создаем тестовые данные на основе реальной структуры из Excel
        test_domains = [
            "NeonGolf.ru", "SpheroidUniverse.ru", "Slim-Secret.ru", 
            "GoodsMail.ru", "BuySocials.nl", "Inter35.ru", "EsperanceCouture.ru"
        ]
        
        test_results = []
        for domain in test_domains:
            # Генерируем тестовые данные для каждого домена
            domain_data = {
                "domain": domain,  # Используем ключ domain для совместимости
                "has_snapshot": True,
                "availability_ts": int(datetime.now().timestamp() * 1000000),
                "total_snapshots": 818 + hash(domain) % 1000,
                "timemap_count": 32 + hash(domain) % 50,
                "first_snapshot": "2018-09-23T21:26:25",
                "last_snapshot": "2025-02-14T05:53:26",
                "avg_interval_days": 2.83 + (hash(domain) % 10) / 10,
                "max_gap_days": 788 + hash(domain) % 200,
                "years_covered": 6 + hash(domain) % 5,
                "snapshots_per_year": json.dumps({
                    "2018": 6, "2019": 13, "2020": 44, 
                    "2022": 5, "2024": 560, "2025": 190
                }),
                "unique_versions": 808 + hash(domain) % 500,
                "is_good": bool(hash(domain) % 2),
                "recommended": True,
                "analysis_time_sec": 3.13 + (hash(domain) % 5),
                "assessment_summary": f"Домен {domain} имеет хорошую историю в архиве."
            }
            test_results.append(domain_data)
        
        # Сохраняем тестовый отчет
        fake_reports_db[report_id] = {
            "id": report_id,
            "report_name": "Тестовый отчет",
            "report_type": "general",
            "task_id": "test-task-123",
            "created_at": created_at,
            "domains_count": len(test_results),
            "filter_criteria": None,
            "results": test_results,
            "domains": ", ".join(test_domains)
        }

# Генерируем тестовые данные при запуске
generate_test_data()

@router.get("/", response_model=PaginatedResponse[ReportResponse])
async def list_reports(
    page: int = Query(1, ge=1, description="Номер страницы"),
    page_size: int = Query(20, ge=1, le=100, description="Количество элементов на странице")
):
    """
    Получить пагинированный список всех отчетов.
    """
    reports_list = [
        ReportResponse(
            id=report_id,
            report_name=report_data["report_name"],
            report_type=report_data["report_type"],
            task_id=report_data["task_id"],
            created_at=report_data["created_at"],
            domains_count=report_data["domains_count"]
        )
        for report_id, report_data in fake_reports_db.items()
    ]
    
    # Применяем пагинацию
    return await paginate(reports_list, page, page_size)

@router.post("/", response_model=ReportResponse)
async def create_report(report_data: ReportCreate):
    """
    Создать новый отчет.
    """
    report_id = str(uuid.uuid4())
    created_at = datetime.utcnow()
    
    # Создаем новый отчет
    report = {
        "id": report_id,
        "report_name": report_data.report_name,
        "report_type": report_data.report_type,
        "task_id": report_data.task_id,
        "created_at": created_at,
        "domains_count": len(report_data.results),
        "filter_criteria": report_data.filter_criteria.dict() if report_data.filter_criteria else None,
        "results": report_data.results,
        "domains": ", ".join([r.get("domain", "") for r in report_data.results])
    }
    
    # Сохраняем отчет в базу данных
    fake_reports_db[report_id] = report
    
    return ReportResponse(
        id=report_id,
        report_name=report_data.report_name,
        report_type=report_data.report_type,
        task_id=report_data.task_id,
        created_at=created_at,
        domains_count=len(report_data.results)
    )

@router.get("/{report_id}", response_model=Dict[str, Any])
async def get_report(report_id: str):
    """
    Получить детальную информацию об отчете по ID.
    """
    if report_id not in fake_reports_db:
        raise HTTPException(status_code=404, detail="Report not found")
    
    report_data = fake_reports_db[report_id]
    
    # Преобразуем данные для совместимости с фронтендом
    results = []
    for item in report_data["results"]:
        # Создаем копию элемента, чтобы не изменять оригинал
        result_item = dict(item)
        
        # Добавляем domain_name для совместимости с фронтендом
        if "domain" in result_item and "domain_name" not in result_item:
            result_item["domain_name"] = result_item["domain"]
        
        # Преобразуем строковые JSON в объекты, если необходимо
        if "snapshots_per_year" in result_item and isinstance(result_item["snapshots_per_year"], str):
            try:
                result_item["snapshots_per_year"] = json.loads(result_item["snapshots_per_year"])
            except json.JSONDecodeError:
                pass  # Оставляем как есть, если не удалось распарсить
        
        results.append(result_item)
    
    # Возвращаем данные в формате, ожидаемом фронтендом
    return {
        "report_id": report_id,
        "report_name": report_data["report_name"],
        "report_type": report_data["report_type"],
        "task_id": report_data["task_id"],
        "created_at": report_data["created_at"],
        "domains_count": report_data["domains_count"],
        "filter_criteria": report_data["filter_criteria"],
        "results": results,
        "domains": report_data.get("domains", "")
    }

@router.delete("/{report_id}", response_model=dict)
async def delete_report(report_id: str):
    """
    Удалить отчет по ID.
    """
    if report_id not in fake_reports_db:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Удаляем отчет из базы данных
    del fake_reports_db[report_id]
    
    return {"message": "Report deleted successfully"}
