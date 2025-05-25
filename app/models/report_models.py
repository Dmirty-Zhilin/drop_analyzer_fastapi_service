from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class ReportCreate(BaseModel):
    """Модель для создания нового отчета."""
    task_id: str = Field(..., description="ID задачи анализа, на основе которой создается отчет")
    report_name: str = Field(..., description="Название отчета")
    report_type: str = Field("general", description="Тип отчета (general, seo, thematic, etc.)")

class ReportListResponse(BaseModel):
    """Модель для отображения отчета в списке."""
    id: str
    task_id: str
    report_name: str
    report_type: str
    domains_count: int
    created_at: str
    updated_at: str

class ReportResponse(BaseModel):
    """Полная модель отчета с результатами анализа."""
    id: str
    task_id: str
    report_name: str
    report_type: str
    domains_count: int
    created_at: str
    updated_at: str
    results: List[Dict[str, Any]] = Field(default_factory=list)
