"""
Модели данных для задач анализа доменов
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class TaskCreate(BaseModel):
    """
    Модель для создания новой задачи анализа доменов
    """
    task_name: str = Field(..., description="Название задачи анализа")
    domains: List[str] = Field(..., description="Список доменов для анализа")
    use_test_data: bool = Field(False, description="Использовать тестовые данные вместо реального анализа")

class TaskResponse(BaseModel):
    """
    Модель для ответа с базовой информацией о задаче
    """
    id: str
    task_name: str
    status: str
    created_at: datetime
    domains_count: int
    progress: Optional[float] = None
    current_domain: Optional[str] = None

class TaskDetailResponse(BaseModel):
    """
    Модель для ответа с детальной информацией о задаче
    """
    id: str
    task_name: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    domains_count: int
    domains: List[str]
    results: List[Dict[str, Any]]
    progress: Optional[float] = None
    current_domain: Optional[str] = None
    error: Optional[str] = None
