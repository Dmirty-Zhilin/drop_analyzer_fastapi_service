from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Dict, Any
from enum import Enum

class AnalysisTaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class DomainInput(BaseModel):
    domain_name: str

class AnalysisTaskCreate(BaseModel):
    domains: List[DomainInput]
    # Add other analysis parameters here, e.g., specific checks to perform

class AnalysisTaskResponse(BaseModel):
    task_id: str
    status: AnalysisTaskStatus
    message: Optional[str] = None
    created_at: Optional[str] = None # Should be datetime, handle conversion
    updated_at: Optional[str] = None # Should be datetime, handle conversion

class DomainAnalysisResult(BaseModel):
    domain_name: str
    # Wayback Machine data
    wayback_history_summary: Optional[Dict[str, Any]] = None
    # Detailed Wayback metrics
    has_snapshot: Optional[bool] = None
    availability_ts: Optional[str] = None
    total_snapshots: Optional[int] = None
    timemap_count: Optional[int] = None
    first_snapshot: Optional[str] = None
    last_snapshot: Optional[str] = None
    avg_interval_days: Optional[float] = None
    max_gap_days: Optional[int] = None
    years_covered: Optional[int] = None
    snapshots_per_year: Optional[str] = None
    unique_versions: Optional[int] = None
    is_good: Optional[bool] = None
    recommended: Optional[bool] = None
    analysis_time_sec: Optional[float] = None
    # Backlinks data
    backlinks_data: Optional[Dict[str, Any]] = None
    # Traffic data
    traffic_data: Optional[Dict[str, Any]] = None
    # SEO Metrics
    seo_metrics: Optional[Dict[str, Any]] = None
    # Thematic Analysis
    thematic_analysis_result: Optional[Dict[str, Any]] = None
    ai_agent_notes: Optional[str] = None
    # Overall assessment
    assessment_score: Optional[float] = None
    assessment_summary: Optional[str] = None

class AnalysisFullReportResponse(AnalysisTaskResponse):
    results: Optional[List[DomainAnalysisResult]] = None

