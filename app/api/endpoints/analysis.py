from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from typing import List, AsyncGenerator
import uuid
import asyncio
import json
from datetime import datetime
import os

from app.models.analysis_models import (
    AnalysisTaskCreate,
    AnalysisTaskResponse,
    AnalysisFullReportResponse,
    AnalysisTaskStatus,
    DomainAnalysisResult,
    DomainInput
)
from app.services.wayback_service import WaybackService
from app.services.openrouter_service import OpenRouterService

# Placeholder for a shared dictionary to store task statuses and results
# In a real application, this would be a database or a distributed cache like Redis
fake_tasks_db: dict = {}

router = APIRouter()

async def process_single_domain(domain_name: str, wayback_service: WaybackService, openrouter_service: OpenRouterService) -> DomainAnalysisResult:
    """Processes a single domain: fetches Wayback history and performs thematic analysis."""
    wayback_history = await wayback_service.get_domain_history_summary(domain_name)
    
    thematic_analysis = None
    simulated_content_for_llm = f"This is placeholder content for {domain_name}. Imagine a full webpage text here."
    if wayback_history.get("error"):
        simulated_content_for_llm = f"Could not fetch content for {domain_name} due to Wayback error: {wayback_history.get('error')}"

    if openrouter_service.api_key:
        thematic_analysis = await openrouter_service.get_thematic_analysis(simulated_content_for_llm, domain_name)
    else:
        thematic_analysis = {"error": "OpenRouter API key not configured. Skipping thematic analysis."}

    return DomainAnalysisResult(
        domain_name=domain_name,
        wayback_history_summary=wayback_history,
        seo_metrics={"DA": None, "PA": None}, 
        thematic_analysis_result=thematic_analysis,
        assessment_score=None, 
        assessment_summary="Assessment pending further data integration."
    )

async def run_domain_analysis_background(task_id: str, domains_to_analyze: List[DomainInput]):
    """Actual background task processing using WaybackService and OpenRouterService."""
    print(f"Starting background analysis for task_id: {task_id} on domains: {[d.domain_name for d in domains_to_analyze]}")
    
    # Update task status to processing immediately
    if task_id in fake_tasks_db:
        fake_tasks_db[task_id]["status"] = AnalysisTaskStatus.PROCESSING
        fake_tasks_db[task_id]["message"] = "Task processing has started."
        fake_tasks_db[task_id]["updated_at"] = datetime.utcnow().isoformat()

    wayback_service = WaybackService()
    openrouter_service = OpenRouterService()

    results = []
    for i, domain_input in enumerate(domains_to_analyze):
        domain_name = domain_input.domain_name
        print(f"Processing domain: {domain_name} for task {task_id} ({i+1}/{len(domains_to_analyze)})")
        # Update status for SSE before processing each domain
        if task_id in fake_tasks_db:
            fake_tasks_db[task_id]["message"] = f"Processing domain {i+1}/{len(domains_to_analyze)}: {domain_name}"
            fake_tasks_db[task_id]["updated_at"] = datetime.utcnow().isoformat()
            # Small delay to allow SSE to potentially pick up the message change
            await asyncio.sleep(0.1)

        try:
            result = await process_single_domain(domain_name, wayback_service, openrouter_service)
            results.append(result)
        except Exception as e:
            print(f"Error processing domain {domain_name} for task {task_id}: {e}")
            results.append(DomainAnalysisResult(
                domain_name=domain_name,
                wayback_history_summary={"error": f"Failed to process: {str(e)}"},
                thematic_analysis_result={"error": f"Failed to process: {str(e)}"}
            ))
    
    if task_id in fake_tasks_db:
        fake_tasks_db[task_id]["status"] = AnalysisTaskStatus.COMPLETED
        fake_tasks_db[task_id]["results"] = [r.model_dump() for r in results]
        fake_tasks_db[task_id]["message"] = "Task completed successfully."
        fake_tasks_db[task_id]["updated_at"] = datetime.utcnow().isoformat()
    print(f"Finished background analysis for task_id: {task_id}")

@router.post("/tasks/", response_model=AnalysisTaskResponse, status_code=202)
async def create_analysis_task(
    task_data: AnalysisTaskCreate,
    background_tasks: BackgroundTasks
):
    task_id = str(uuid.uuid4())
    current_time = datetime.utcnow().isoformat()
    
    task_info = {
        "task_id": task_id,
        "status": AnalysisTaskStatus.PENDING,
        "message": "Task received and queued for processing.",
        "created_at": current_time,
        "updated_at": current_time,
        "domains_submitted": [d.domain_name for d in task_data.domains],
        "results": [] 
    }
    fake_tasks_db[task_id] = task_info

    background_tasks.add_task(run_domain_analysis_background, task_id, task_data.domains)
    
    # Status will be updated by the background task itself to PROCESSING
    # fake_tasks_db[task_id]["status"] = AnalysisTaskStatus.PROCESSING 
    # fake_tasks_db[task_id]["message"] = "Task is now being processed."

    return AnalysisTaskResponse(
        task_id=task_id,
        status=fake_tasks_db[task_id]["status"],
        message=fake_tasks_db[task_id]["message"],
        created_at=current_time,
        updated_at=current_time
    )

@router.get("/tasks/{task_id}/status", response_model=AnalysisTaskResponse)
async def get_task_status_http(task_id: str): # Renamed to avoid conflict if SSE is also named get_task_status
    task = fake_tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return AnalysisTaskResponse(**dict(task))

@router.get("/tasks/{task_id}/report", response_model=AnalysisFullReportResponse)
async def get_task_report(task_id: str):
    task = fake_tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task["status"] != AnalysisTaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Task is not yet completed. Current status: {task['status']}")
    return AnalysisFullReportResponse(**dict(task))

async def sse_task_status_generator(task_id: str, request: Request) -> AsyncGenerator[str, None]:
    """Streams status updates for a given task_id."""
    last_sent_status_json = None
    if task_id not in fake_tasks_db:
        yield f"event: error\ndata: {json.dumps({'error': 'Task not found'})}\n\n"
        return

    while True:
        # Check if client disconnected
        if await request.is_disconnected():
            print(f"Client for task {task_id} disconnected from SSE stream.")
            break

        task_info = fake_tasks_db.get(task_id)
        if not task_info: # Should have been caught above, but as a safeguard
            yield f"event: error\ndata: {json.dumps({'error': 'Task disappeared'})}\n\n"
            break
        
        current_status_json = json.dumps({
            "task_id": task_info["task_id"],
            "status": task_info["status"],
            "message": task_info.get("message", ""),
            "updated_at": task_info.get("updated_at", datetime.utcnow().isoformat())
        })

        if current_status_json != last_sent_status_json:
            yield f"data: {current_status_json}\n\n"
            last_sent_status_json = current_status_json
        
        if task_info["status"] == AnalysisTaskStatus.COMPLETED or task_info["status"] == AnalysisTaskStatus.FAILED:
            # Send one last update and then close
            yield f"event: complete\ndata: {current_status_json}\n\n" # Custom event for completion/failure
            break
        
        await asyncio.sleep(1) # Poll interval

@router.get("/tasks/{task_id}/stream-status")
async def stream_task_status(task_id: str, request: Request):
    """Endpoint to stream task status updates using SSE."""
    if task_id not in fake_tasks_db:
        raise HTTPException(status_code=404, detail="Task not found for SSE streaming.")
    return StreamingResponse(sse_task_status_generator(task_id, request), media_type="text/event-stream")


