from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional

from app.models.reports.report_models import (
    ReportCreate,
    Report,
    ReportResponse,
    ReportDetailResponse,
    ReportType,
    FilterCriteria
)

# Placeholder for a shared dictionary to store reports
# In a real application, this would be a database or a distributed cache
fake_reports_db: dict = {}

router = APIRouter()

def apply_filter_criteria(domain_data: dict, criteria: FilterCriteria) -> bool:
    """Apply filter criteria to domain data to determine if it should be included in the report."""
    if not domain_data:
        return False
    
    # Extract values with safe fallbacks
    total_snapshots = domain_data.get("total_snapshots", 0) or 0
    years_covered = domain_data.get("years_covered", 0) or 0
    avg_interval_days = domain_data.get("avg_interval_days", float('inf')) or float('inf')
    max_gap_days = domain_data.get("max_gap_days", float('inf')) or float('inf')
    timemap_count = domain_data.get("timemap_count", 0) or 0
    
    # Apply criteria
    return (
        total_snapshots >= criteria.min_snapshots and
        years_covered >= criteria.min_years and
        avg_interval_days <= criteria.max_avg_interval and
        max_gap_days <= criteria.max_gap and
        timemap_count >= criteria.min_timemap
    )

@router.post("/", response_model=ReportResponse)
async def create_report(report_data: ReportCreate):
    """Create a new report from analysis task results."""
    from app.api.endpoints.analysis import fake_tasks_db  # Import here to avoid circular imports
    
    # Check if task exists and is completed
    task = fake_tasks_db.get(report_data.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Analysis task not found")
    
    if task.get("status") != "completed":
        raise HTTPException(status_code=400, detail=f"Task is not completed. Current status: {task.get('status')}")
    
    # Create new report
    report = Report(
        report_name=report_data.report_name,
        report_type=report_data.report_type,
        filter_criteria=report_data.filter_criteria,
        task_id=report_data.task_id,
    )
    
    # Filter results if needed
    all_results = task.get("results", [])
    if report_data.report_type == ReportType.FILTERED and report_data.filter_criteria:
        report.results = [
            result for result in all_results 
            if apply_filter_criteria(result, report_data.filter_criteria)
        ]
    else:
        report.results = all_results
    
    report.domains_count = len(report.results)
    
    # Save report
    fake_reports_db[report.id] = report.model_dump()
    
    return ReportResponse(
        id=report.id,
        report_name=report.report_name,
        report_type=report.report_type,
        task_id=report.task_id,
        created_at=report.created_at,
        domains_count=report.domains_count
    )

@router.get("/", response_model=List[ReportResponse])
async def list_reports():
    """Get a list of all reports."""
    return [
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

@router.get("/{report_id}", response_model=ReportDetailResponse)
async def get_report(report_id: str):
    """Get detailed report data by ID."""
    report_data = fake_reports_db.get(report_id)
    if not report_data:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return ReportDetailResponse(**report_data)

@router.delete("/{report_id}", status_code=204)
async def delete_report(report_id: str):
    """Delete a report by ID."""
    if report_id not in fake_reports_db:
        raise HTTPException(status_code=404, detail="Report not found")
    
    del fake_reports_db[report_id]
    return None
