""" Модуль для анализа доменов через Wayback Machine API.
Адаптирован из way2_fixed.py для использования в FastAPI сервисе.
Оптимизирован для лучшей обработки ошибок и управления памятью.
"""
import asyncio
import json
import logging
import statistics
from datetime import datetime
from typing import List, Dict, Any, Optional

import aiohttp

from app.utils.error_handlers import (
    retry_async,
    safe_request,
    NetworkError,
    ServerError,
    ResourceNotFoundError
)

# Конфигурация
CDX_API = "https://web.archive.org/cdx/search/cdx"
AVAIL_API = "https://archive.org/wayback/available"
TIMEMAP_URL = "http://web.archive.org/web/timemap/link/{url}"
REQUEST_TIMEOUT = 30  # секунд
DEFAULT_CONCURRENCY = 5  # Ограничение на количество одновременных запросов
DEFAULT_BATCH_SIZE = 100  # Размер пакета для обработки доменов

# Критерии для long-live доменов (из way2_fixed.py)
LONG_LIVE_MIN_SNAPSHOTS = 5
LONG_LIVE_MIN_YEARS = 3
LONG_LIVE_MAX_AVG_INTERVAL = 90
LONG_LIVE_MAX_GAP = 180
LONG_LIVE_MIN_TIMEMAP = 200

# Критерии для рекомендованных доменов (из way2_fixed.py)
RECOMMENDED_MIN_SNAPSHOTS = 200
RECOMMENDED_MAX_AVG_INTERVAL = 30

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def analyze_domain(domain: str, session: aiohttp.ClientSession, limit: int = 1000, match_type: str = "domain", collapse: str = "digest") -> dict:
    """Собираем метрики по одному домену."""
    info = {"domain_name": domain}  # Используем domain_name для совместимости с frontend
    start = datetime.utcnow()
    
    # Availability API
    avail_params = {"url": f"http://{domain}"}  # Исправление: добавляем протокол http:// к URL
    avail = await retry_async(
        safe_request,
        session,
        "GET",
        AVAIL_API,
        params=avail_params,
        max_retries=3,
        delay=1.0
    )
    
    if avail and isinstance(avail, dict) and avail.get("archived_snapshots", {}).get("closest"):
        closest = avail["archived_snapshots"]["closest"]
        info["has_snapshot"] = bool(closest.get("available"))
        info["availability_ts"] = closest.get("timestamp")
    else:
        logger.warning(f"Could not retrieve availability for {domain}. Response: {avail}")
        info["has_snapshot"] = False
        info["availability_ts"] = None
    
    # CDX API
    records = []
    offset = 0
    base_cdx_params = {
        "url": domain,
        "matchType": match_type,
        "output": "json",
        "fl": "timestamp,original,digest",
        "limit": limit
    }
    
    if collapse:
        base_cdx_params["collapse"] = collapse
        
    while True:
        cdx_params = {**base_cdx_params, "offset": offset}
        batch = await retry_async(
            safe_request,
            session,
            "GET",
            CDX_API,
            params=cdx_params,
            max_retries=3,
            delay=1.0
        )
        
        if not batch or not isinstance(batch, list) or len(batch) < 1:
            if isinstance(batch, list) and len(batch) == 1 and batch[0] == ['timestamp', 'original', 'digest']:
                logger.info(f"CDX API returned only headers for {domain} with offset {offset}. Assuming no more data.")
            elif not batch:
                logger.warning(f"CDX API returned empty or invalid batch for {domain} with offset {offset}. Batch: {batch}")
            break
            
        # Обработка данных из CDX API
        current_records = []
        if isinstance(batch[0], list):  # Заголовки присутствуют
            if len(batch) < 2:  # Только заголовки, нет данных
                logger.info(f"CDX API returned only headers for {domain} with offset {offset}. No data rows.")
                break
                
            cols = batch[0]
            for row in batch[1:]:
                if isinstance(row, list) and len(row) == len(cols):
                    records.append(dict(zip(cols, row)))
                    current_records.append(dict(zip(cols, row)))
                else:
                    logger.warning(f"Skipping malformed row in CDX batch for {domain}: {row}")
                    
        elif isinstance(batch[0], dict):  # Данные без заголовков
            for item in batch:
                if isinstance(item, dict):
                    records.append(item)
                    current_records.append(item)
                else:
                    logger.warning(f"Skipping malformed item in CDX batch for {domain}: {item}")
        else:
            logger.warning(f"Unexpected CDX batch format for {domain} with offset {offset}. Batch: {batch}")
            break
            
        if len(current_records) < limit:
            break
            
        offset += limit
        if offset > 50000 and limit > 0:
            logger.warning(f"Reached max offset (50000) for {domain}. Stopping CDX pagination.")
            break
            
    info["total_snapshots"] = len(records)
    
    # Timemap count
    tm_url = TIMEMAP_URL.format(url=f"http://{domain}")  # Исправление: добавляем протокол http:// к URL
    tm_text = await retry_async(
        safe_request,
        session,
        "GET",
        tm_url,
        max_retries=3,
        delay=1.0
    )
    info["timemap_count"] = tm_text.count("web/") if tm_text and isinstance(tm_text, str) else 0
    
    # Метрики снимков
    if records:
        try:
            times = sorted([r["timestamp"] for r in records if "timestamp" in r and r["timestamp"] is not None])
            dates = [datetime.strptime(ts, "%Y%m%d%H%M%S") for ts in times if len(ts) == 14]
            
            if dates:
                # Преобразуем даты в строки для совместимости с JSON
                info["first_snapshot"] = dates[0].strftime("%Y-%m-%d")
                info["last_snapshot"] = dates[-1].strftime("%Y-%m-%d")
                
                gaps = [(dates[i] - dates[i-1]).days for i in range(1, len(dates))]
                info["avg_interval_days"] = round(statistics.mean(gaps), 2) if gaps else 0
                info["max_gap_days"] = max(gaps) if gaps else 0
                
                years = {d.year for d in dates}
                info["years_covered"] = len(years)
                info["snapshots_per_year"] = {str(y): sum(1 for d in dates if d.year==y) for y in sorted(list(years))}
                info["unique_versions"] = len({r["digest"] for r in records if "digest" in r})
            else:
                logger.warning(f"No valid dates found for {domain} despite having records. Timestamps: {times}")
        except Exception as e:
            logger.error(f"Error calculating metrics for {domain}: {e}")
            # Устанавливаем значения по умолчанию при ошибке
            info.update({
                "first_snapshot": None,
                "last_snapshot": None,
                "avg_interval_days": 0,
                "max_gap_days": 0,
                "years_covered": 0,
                "snapshots_per_year": {},
                "unique_versions": 0
            })
    else:
        # Устанавливаем значения по умолчанию при отсутствии записей
        info.update({
            "first_snapshot": None,
            "last_snapshot": None,
            "avg_interval_days": 0,
            "max_gap_days": 0,
            "years_covered": 0,
            "snapshots_per_year": {},
            "unique_versions": 0
        })
    
    # Определяем статус домена
    info["is_good"] = (
        info["total_snapshots"] >= LONG_LIVE_MIN_SNAPSHOTS and
        info["years_covered"] >= LONG_LIVE_MIN_YEARS and
        info["avg_interval_days"] <= LONG_LIVE_MAX_AVG_INTERVAL and
        info["max_gap_days"] <= LONG_LIVE_MAX_GAP and
        info["timemap_count"] >= LONG_LIVE_MIN_TIMEMAP
    )
    
    info["is_long_live"] = info["is_good"]
    
    info["recommended"] = (
        info["total_snapshots"] >= RECOMMENDED_MIN_SNAPSHOTS and
        info["avg_interval_days"] <= RECOMMENDED_MAX_AVG_INTERVAL
    )
    
    # Добавляем время анализа
    info["analysis_time_sec"] = round((datetime.utcnow() - start).total_seconds(), 2)
    
    return info

async def analyze_domains(domains: List[str], concurrency: int = DEFAULT_CONCURRENCY, batch_size: int = DEFAULT_BATCH_SIZE) -> List[dict]:
    """Анализирует список доменов с ограничением параллельных запросов."""
    semaphore = asyncio.Semaphore(concurrency)
    results = []
    
    async def analyze_with_semaphore(domain):
        async with semaphore:
            try:
                async with aiohttp.ClientSession() as session:
                    return await analyze_domain(domain, session)
            except Exception as e:
                logger.error(f"Error analyzing domain {domain}: {e}")
                return {
                    "domain_name": domain,
                    "error": str(e),
                    "has_snapshot": False,
                    "total_snapshots": 0,
                    "is_good": False,
                    "is_long_live": False,
                    "recommended": False
                }
    
    # Разбиваем домены на батчи
    for i in range(0, len(domains), batch_size):
        batch = domains[i:i + batch_size]
        tasks = [analyze_with_semaphore(domain) for domain in batch]
        batch_results = await asyncio.gather(*tasks)
        results.extend(batch_results)
    
    return results
