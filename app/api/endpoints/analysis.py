from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Body
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
import pandas as pd
import io
import csv
import tempfile
import os
from weasyprint import HTML, CSS
from typing import List, AsyncGenerator, Dict
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

# Константа для ограничения количества одновременных задач
MAX_CONCURRENT_DOMAINS = 10

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

    # Извлекаем все необходимые метрики из wayback_history
    has_snapshot = wayback_history.get("has_snapshot", False)
    availability_ts = wayback_history.get("availability_ts")
    total_snapshots = wayback_history.get("total_snapshots", 0)
    timemap_count = wayback_history.get("timemap_count", 0)
    first_snapshot = wayback_history.get("first_snapshot")
    last_snapshot = wayback_history.get("last_snapshot")
    avg_interval_days = wayback_history.get("avg_interval_days")
    max_gap_days = wayback_history.get("max_gap_days")
    years_covered = wayback_history.get("years_covered")
    snapshots_per_year = wayback_history.get("snapshots_per_year")
    unique_versions = wayback_history.get("unique_versions")
    is_good = wayback_history.get("is_good", False)
    recommended = wayback_history.get("recommended", False)
    analysis_time_sec = wayback_history.get("analysis_time_sec")

    return DomainAnalysisResult(
        domain_name=domain_name,
        wayback_history_summary=wayback_history,
        seo_metrics={"DA": None, "PA": None}, 
        thematic_analysis_result=thematic_analysis,
        assessment_score=None, 
        assessment_summary="Assessment pending further data integration.",
        # Добавляем все расширенные метрики
        has_snapshot=has_snapshot,
        availability_ts=availability_ts,
        total_snapshots=total_snapshots,
        timemap_count=timemap_count,
        first_snapshot=first_snapshot,
        last_snapshot=last_snapshot,
        avg_interval_days=avg_interval_days,
        max_gap_days=max_gap_days,
        years_covered=years_covered,
        snapshots_per_year=snapshots_per_year,
        unique_versions=unique_versions,
        is_good=is_good,
        recommended=recommended,
        analysis_time_sec=analysis_time_sec
    )

async def process_domains_batch(domains_batch: List[DomainInput], wayback_service: WaybackService, openrouter_service: OpenRouterService, task_id: str, batch_index: int, total_batches: int, total_domains: int):
    """Обрабатывает пакет доменов параллельно"""
    results = []
    start_index = batch_index * len(domains_batch)
    
    # Обновляем статус задачи перед обработкой пакета
    if task_id in fake_tasks_db:
        fake_tasks_db[task_id]["message"] = f"Обработка пакета {batch_index + 1}/{total_batches} ({start_index + 1}-{min(start_index + len(domains_batch), total_domains)}/{total_domains} доменов)"
        fake_tasks_db[task_id]["updated_at"] = datetime.utcnow().isoformat()
    
    # Создаем список задач для параллельного выполнения
    tasks = []
    for domain_input in domains_batch:
        domain_name = domain_input.domain_name
        tasks.append(process_single_domain(domain_name, wayback_service, openrouter_service))
    
    # Выполняем все задачи параллельно
    batch_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Обрабатываем результаты, преобразуя исключения в сообщения об ошибках
    for i, result in enumerate(batch_results):
        domain_name = domains_batch[i].domain_name
        if isinstance(result, Exception):
            print(f"Error processing domain {domain_name}: {result}")
            results.append(DomainAnalysisResult(
                domain_name=domain_name,
                wayback_history_summary={"error": f"Failed to process: {str(result)}"},
                thematic_analysis_result={"error": f"Failed to process: {str(result)}"}
            ))
        else:
            results.append(result)
    
    return results

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

    # Разбиваем домены на пакеты для параллельной обработки
    total_domains = len(domains_to_analyze)
    batch_size = MAX_CONCURRENT_DOMAINS  # Максимальное количество одновременно обрабатываемых доменов
    batches = [domains_to_analyze[i:i + batch_size] for i in range(0, total_domains, batch_size)]
    total_batches = len(batches)
    
    all_results = []
    for i, batch in enumerate(batches):
        # Обрабатываем каждый пакет доменов параллельно
        batch_results = await process_domains_batch(
            batch, wayback_service, openrouter_service, 
            task_id, i, total_batches, total_domains
        )
        all_results.extend(batch_results)
        
        # Небольшая пауза между пакетами для обновления статуса
        await asyncio.sleep(0.1)
    
    if task_id in fake_tasks_db:
        fake_tasks_db[task_id]["status"] = AnalysisTaskStatus.COMPLETED
        fake_tasks_db[task_id]["results"] = [r.model_dump() for r in all_results]
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
async def get_task_report(task_id: str, filter_type: str = None):
    task = fake_tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task["status"] != AnalysisTaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Task is not yet completed. Current status: {task['status']}")
    
    # Создаем копию задачи для возможной фильтрации
    filtered_task = dict(task)
    
    # Если указан тип фильтра "long-live", применяем фильтрацию по 4 параметрам
    if filter_type == "long-live" and "results" in filtered_task:
        filtered_results = []
        for result in filtered_task["results"]:
            # Проверяем условия для long-live доменов
            total_snapshots = result.get("total_snapshots", 0)
            years_covered = result.get("years_covered", 0)
            avg_interval_days = result.get("avg_interval_days", float('inf'))
            max_gap_days = result.get("max_gap_days", float('inf'))
            
            # Применяем 4 параметра фильтрации для long-live доменов
            if (total_snapshots >= 5 and 
                years_covered >= 3 and 
                avg_interval_days is not None and avg_interval_days < 90 and 
                max_gap_days is not None and max_gap_days < 180):
                filtered_results.append(result)
        
        filtered_task["results"] = filtered_results
    
    return AnalysisFullReportResponse(**filtered_task)

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

@router.post("/settings/openrouter")
async def save_openrouter_settings(settings: Dict = Body(...)):
    """Сохраняет ключ API OpenRouter в файл конфигурации."""
    api_key = settings.get("api_key")
    if not api_key or not isinstance(api_key, str) or api_key.strip() == "":
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "API ключ не может быть пустым"}
        )
    
    # Создаем экземпляр сервиса и сохраняем ключ
    service = OpenRouterService()
    success = service.set_api_key(api_key)
    
    if success:
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "Настройки успешно сохранены"}
        )
    else:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Не удалось сохранить настройки"}
        )

@router.get("/settings/openrouter")
async def get_openrouter_settings():
    """Получает текущие настройки OpenRouter."""
    service = OpenRouterService()
    return JSONResponse(
        status_code=200,
        content={"api_key": service.api_key or ""}
    )

@router.get("/tasks/{task_id}/download")
async def download_report(task_id: str, format: str = "excel", filter_type: str = None):
    """Download report in various formats (excel, csv, pdf)"""
    task = fake_tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task["status"] != AnalysisTaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Task is not yet completed. Current status: {task['status']}")
    
    # Получаем результаты с учетом фильтрации
    filtered_task = dict(task)
    
    # Если указан тип фильтра "long-live", применяем фильтрацию по 4 параметрам
    if filter_type == "long-live" and "results" in filtered_task:
        filtered_results = []
        for result in filtered_task["results"]:
            # Проверяем условия для long-live доменов
            total_snapshots = result.get("total_snapshots", 0)
            years_covered = result.get("years_covered", 0)
            avg_interval_days = result.get("avg_interval_days", float('inf'))
            max_gap_days = result.get("max_gap_days", float('inf'))
            
            # Применяем 4 параметра фильтрации для long-live доменов
            if (total_snapshots >= 5 and 
                years_covered >= 3 and 
                avg_interval_days is not None and avg_interval_days < 90 and 
                max_gap_days is not None and max_gap_days < 180):
                filtered_results.append(result)
        
        filtered_task["results"] = filtered_results
    
    # Преобразуем результаты в DataFrame для удобства экспорта
    data = []
    for result in filtered_task.get("results", []):
        data.append({
            "Домен": result.get("domain_name", ""),
            "Снимки": result.get("total_snapshots", 0),
            "Первый снимок": result.get("first_snapshot", ""),
            "Последний снимок": result.get("last_snapshot", ""),
            "Лет": result.get("years_covered", 0),
            "Ср. интервал": result.get("avg_interval_days", 0),
            "Макс. промежуток": result.get("max_gap_days", 0),
            "Timemap": result.get("timemap_count", 0),
            "Рекомендуемый": "Да" if result.get("recommended", False) else "Нет",
            "Long-live": "Да" if (result.get("total_snapshots", 0) >= 5 and 
                                result.get("years_covered", 0) >= 3 and 
                                result.get("avg_interval_days", float('inf')) < 90 and 
                                result.get("max_gap_days", float('inf')) < 180) else "Нет"
        })
    
    df = pd.DataFrame(data)
    
    # Формируем имя файла
    report_type = "long_live" if filter_type == "long-live" else "full"
    filename_base = f"drop_report_{report_type}_{task_id[:8]}"
    
    if format.lower() == "excel":
        # Экспорт в Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Отчет', index=False)
            # Настройка форматирования
            workbook = writer.book
            worksheet = writer.sheets['Отчет']
            header_format = workbook.add_format({'bold': True, 'bg_color': '#D9D9D9', 'border': 1})
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
            # Автоподбор ширины столбцов
            for i, col in enumerate(df.columns):
                column_width = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.set_column(i, i, column_width)
        
        output.seek(0)
        filename = f"{filename_base}.xlsx"
        headers = {'Content-Disposition': f'attachment; filename="{filename}"'}
        return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)
    
    elif format.lower() == "csv":
        # Экспорт в CSV
        output = io.StringIO()
        df.to_csv(output, index=False, quoting=csv.QUOTE_NONNUMERIC)
        output.seek(0)
        filename = f"{filename_base}.csv"
        headers = {'Content-Disposition': f'attachment; filename="{filename}"'}
        return StreamingResponse(io.BytesIO(output.getvalue().encode('utf-8')), media_type="text/csv", headers=headers)
    
    elif format.lower() == "pdf":
        # Экспорт в PDF
        # Создаем временный HTML файл
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as f:
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Domain Analysis Report</title>
                <style>
                    body {{ font-family: Arial, sans-serif; }}
                    table {{ border-collapse: collapse; width: 100%; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                    th {{ background-color: #f2f2f2; }}
                    tr:nth-child(even) {{ background-color: #f9f9f9; }}
                </style>
            </head>
            <body>
                <h1>Domain Analysis Report</h1>
                <p>Task ID: {task_id}</p>
                <p>Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                {df.to_html(index=False)}
            </body>
            </html>
            """
            f.write(html_content.encode('utf-8'))
            html_path = f.name
        
        # Создаем PDF из HTML
        pdf_path = html_path.replace('.html', '.pdf')
        HTML(html_path).write_pdf(pdf_path)
        
        # Удаляем временный HTML файл
        os.unlink(html_path)
        
        # Возвращаем PDF файл
        filename = f"{filename_base}.pdf"
        headers = {'Content-Disposition': f'attachment; filename="{filename}"'}
        return FileResponse(pdf_path, media_type="application/pdf", headers=headers, filename=filename)
    
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}. Supported formats: excel, csv, pdf")
