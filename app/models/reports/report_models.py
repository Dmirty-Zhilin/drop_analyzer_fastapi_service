from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid

class ReportType(str, Enum):
    GENERAL = "general"
    FILTERED = "filtered"

class FilterCriteria(BaseModel):
    min_snapshots: int = Field(5, description="Minimum number of snapshots")
    min_years: int = Field(3, description="Minimum years covered")
    max_avg_interval: float = Field(90.0, description="Maximum average interval in days")
    max_gap: int = Field(180, description="Maximum gap in days")
    min_timemap: int = Field(200, description="Minimum timemap count")

class ReportCreate(BaseModel):
    report_name: str = Field(..., description="Name of the report")
    report_type: ReportType = Field(..., description="Type of report (general or filtered)")
    filter_criteria: Optional[FilterCriteria] = Field(None, description="Filter criteria for filtered reports")
    task_id: str = Field(..., description="ID of the analysis task")

class Report(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique report ID")
    report_name: str = Field(..., description="Name of the report")
    report_type: ReportType = Field(..., description="Type of report (general or filtered)")
    filter_criteria: Optional[FilterCriteria] = Field(None, description="Filter criteria for filtered reports")
    task_id: str = Field(..., description="ID of the analysis task")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Report creation timestamp")
    domains_count: int = Field(0, description="Number of domains in the report")
    results: List[Dict[str, Any]] = Field([], description="Domain analysis results")

class ReportResponse(BaseModel):
    id: str = Field(..., description="Unique report ID")
    report_name: str = Field(..., description="Name of the report")
    report_type: ReportType = Field(..., description="Type of report (general or filtered)")
    task_id: str = Field(..., description="ID of the analysis task")
    created_at: datetime = Field(..., description="Report creation timestamp")
    domains_count: int = Field(..., description="Number of domains in the report")

class ReportDetailResponse(ReportResponse):
    filter_criteria: Optional[FilterCriteria] = Field(None, description="Filter criteria for filtered reports")
    results: List[Dict[str, Any]] = Field(..., description="Domain analysis results")
