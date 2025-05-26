"""
Обновленный модуль reports.py с пагинацией и улучшенной обработкой ошибок
"""
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import uuid

from app.utils.pagination import paginate, PaginatedResponse
from app.models.reports.report_models import ReportCreate, ReportResponse, ReportDetailResponse

router = APIRouter()

# Временное хранилище отчетов (в реальном приложении должно быть заменено на базу данных)
fake_reports_db = {}

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
        "results": report_data.results
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

@router.get("/{report_id}", response_model=ReportDetailResponse)
async def get_report(report_id: str):
    """
    Получить детальную информацию об отчете по ID.
    """
    if report_id not in fake_reports_db:
        raise HTTPException(status_code=404, detail="Report not found")
    
    report_data = fake_reports_db[report_id]
    
    return ReportDetailResponse(
        id=report_id,
        report_name=report_data["report_name"],
        report_type=report_data["report_type"],
        task_id=report_data["task_id"],
        created_at=report_data["created_at"],
        domains_count=report_data["domains_count"],
        filter_criteria=report_data["filter_criteria"],
        results=report_data["results"]
    )

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
