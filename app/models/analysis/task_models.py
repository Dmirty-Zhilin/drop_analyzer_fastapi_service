"""
Модели для задач анализа доменов
"""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class TaskCreate(BaseModel):
    """
    Модель для создания новой задачи анализа
    """
    task_name: str
    domains: List[str]

class TaskResponse(BaseModel):
    """
    Модель для ответа с базовой информацией о задаче
    """
    id: str
    task_name: str
    status: str
    created_at: datetime
    domains_count: int

class TaskDetailResponse(BaseModel):
    """
    Модель для детального ответа о задаче с результатами
    """
    id: str
    task_name: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    domains_count: int
    domains: List[str]
    results: List[Dict[str, Any]] = []
