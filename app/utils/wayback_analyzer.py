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

# Конфигурация
CDX_API = "https://web.archive.org/cdx/search/cdx"
AVAIL_API = "https://archive.org/wayback/available"
TIMEMAP_URL = "http://web.archive.org/web/timemap/link/{url}"
REQUEST_TIMEOUT = 30  # секунд
RETRY_DELAY = 2  # секунд
RETRY_COUNT = 3
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

async def safe_request(session: aiohttp.ClientSession, method: str, url: str, **kwargs):
    """Универсальный безопасный запрос с ретраями."""
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            async with session.request(method, url, timeout=REQUEST_TIMEOUT, **kwargs) as resp:
                resp.raise_for_status()  # Проверка на HTTP ошибки (4xx, 5xx)
                
                if kwargs.get("params", {}).get("output") == "json" or "application/json" in resp.headers.get("Content-Type", ""):
                    # Проверка, что ответ действительно JSON перед парсингом
                    text_content = await resp.text()  # Сначала читаем как текст
                    
                    if not text_content.strip():  # Если ответ пустой
                        logger.warning(f"[{attempt}/{RETRY_COUNT}] Empty JSON response from {url} with params {kwargs.get('params')}")
                        return None
                    
                    try:
                        return json.loads(text_content)  # Затем парсим JSON
                    except json.JSONDecodeError as je:
                        logger.error(f"[{attempt}/{RETRY_COUNT}] JSON decode error for {url} {kwargs.get('params')}: {je}. Response text: {text_content[:200]}")
                        if attempt == RETRY_COUNT:
                            return None
                else:
                    return await resp.text()
                    
        except aiohttp.ClientResponseError as e:
            logger.warning(f"[{attempt}/{RETRY_COUNT}] HTTP error {e.status} for {url} {kwargs.get('params')}: {e.message}")
            
            if e.status == 429:  # Too Many Requests
                logger.info(f"Rate limit hit for {url}. Sleeping for {RETRY_DELAY * attempt * 2} seconds.")
                await asyncio.sleep(RETRY_DELAY * attempt * 2)  # Увеличенная задержка для 429
            elif e.status >= 500:  # Server errors
                await asyncio.sleep(RETRY_DELAY * attempt)
            elif attempt == RETRY_COUNT:
                logger.error(f"Failed to fetch {url} after {RETRY_COUNT} attempts due to HTTP {e.status}.")
                return None
                
        except asyncio.TimeoutError:
            logger.warning(f"[{attempt}/{RETRY_COUNT}] Timeout error for {url} {kwargs.get('params')}")
            if attempt == RETRY_COUNT:
                logger.error(f"Failed to fetch {url} after {RETRY_COUNT} attempts due to timeout.")
                return None
                
        except aiohttp.ClientError as e:  # Другие ошибки клиента (например, проблемы с соединением)
            logger.warning(f"[{attempt}/{RETRY_COUNT}] Client error for {url} {kwargs.get('params')}: {e}")
            if attempt == RETRY_COUNT:
                logger.error(f"Failed to fetch {url} after {RETRY_COUNT} attempts due to client error.")
                return None
                
        except Exception as e:
            logger.error(f"[{attempt}/{RETRY_COUNT}] Unexpected error for {url} {kwargs.get('params')}: {e}")
            if attempt == RETRY_COUNT:
                return None
                
        if attempt < RETRY_COUNT:
            await asyncio.sleep(RETRY_DELAY * attempt)  # Экспоненциальная задержка
            
    return None

async def analyze_domain(domain: str, session: aiohttp.ClientSession, limit: int = 1000, match_type: str = "domain", collapse: str = "digest") -> dict:
    """Собираем метрики по одному домену."""
    info = {"domain_name": domain}  # Используем domain_name для совместимости с frontend
    start = datetime.utcnow()
    
    # Availability API
    avail_params = {"url": f"http://{domain}"}  # Исправление: добавляем протокол http:// к URL
    avail = await safe_request(session, "GET", AVAIL_API, params=avail_params)
    
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
        batch = await safe_request(session, "GET", CDX_API, params=cdx_params)
        
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
    tm_text = await safe_request(session, "GET", tm_url)
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
                for k in ("first_snapshot", "last_snapshot", "avg_interval_days", "max_gap_days", "years_covered", "snapshots_per_year", "unique_versions"):
                    info[k] = None
        except Exception as e:
            logger.error(f"Error processing snapshot metrics for {domain}: {e}. Records: {records[:5]}")
            for k in ("first_snapshot", "last_snapshot", "avg_interval_days", "max_gap_days", "years_covered", "snapshots_per_year", "unique_versions"):
                info[k] = None
    else:
        for k in ("first_snapshot", "last_snapshot", "avg_interval_days", "max_gap_days", "years_covered", "snapshots_per_year", "unique_versions"):
            info[k] = None
    
    # Оценка домена по строгим критериям из way2_fixed.py
    try:
        # Проверка на long-live домен (все 5 критериев должны выполняться)
        is_long_live = (
            info["total_snapshots"] >= LONG_LIVE_MIN_SNAPSHOTS and
            info.get("years_covered") is not None and info["years_covered"] >= LONG_LIVE_MIN_YEARS and
            info.get("avg_interval_days") is not None and info["avg_interval_days"] < LONG_LIVE_MAX_AVG_INTERVAL and
            info.get("max_gap_days") is not None and info["max_gap_days"] < LONG_LIVE_MAX_GAP and
            info["timemap_count"] > LONG_LIVE_MIN_TIMEMAP
        )
        
        # Проверка на рекомендованный домен (оба критерия должны выполняться)
        is_recommended = (
            info["total_snapshots"] >= RECOMMENDED_MIN_SNAPSHOTS and
            info.get("avg_interval_days") is not None and info["avg_interval_days"] < RECOMMENDED_MAX_AVG_INTERVAL
        )
        
        info["is_long_live"] = is_long_live
        info["recommended"] = is_recommended
        
        # Текстовая сводка на основе критериев
        if is_long_live and is_recommended:
            info["assessment_summary"] = "Отличный домен с богатой историей и регулярными снимками. Рекомендуется для использования."
        elif is_long_live:
            info["assessment_summary"] = "Хороший домен с долгой историей, но недостаточно частыми снимками для рекомендации."
        elif is_recommended:
            info["assessment_summary"] = "Домен с частыми снимками, но недостаточно долгой историей для статуса long-live."
        else:
            info["assessment_summary"] = "Домен не соответствует критериям long-live и не рекомендуется."
        
        # Сохраняем оценку для совместимости с frontend
        score = 0
        if info["total_snapshots"] > 0:
            if is_long_live:
                score += 10
            if is_recommended:
                score += 10
            
            # Дополнительные баллы для градации
            score += min(info["total_snapshots"] / 100, 5)
            if info["years_covered"]:
                score += min(info["years_covered"], 5)
        
        info["assessment_score"] = round(score, 1)
        
    except Exception as e:
        logger.error(f"Error calculating assessment for {domain}: {e}")
        info["is_long_live"] = False
        info["recommended"] = False
        info["assessment_score"] = 0
        info["assessment_summary"] = "Ошибка при оценке домена."
    
    # Время выполнения
    info["analysis_time_ms"] = (datetime.utcnow() - start).total_seconds() * 1000
    
    return info

async def analyze_domains(domains: List[str], concurrency: int = DEFAULT_CONCURRENCY, batch_size: int = DEFAULT_BATCH_SIZE) -> List[dict]:
    """Анализирует список доменов с ограничением на количество одновременных запросов и размер пакета."""
    all_results = []
    
    # Обрабатываем домены пакетами для экономии памяти
    for i in range(0, len(domains), batch_size):
        batch_domains = domains[i:i+batch_size]
        logger.info(f"Processing batch {i//batch_size + 1}/{(len(domains) + batch_size - 1)//batch_size} ({len(batch_domains)} domains)")
        
        semaphore = asyncio.Semaphore(concurrency)
        
        async def analyze_with_semaphore(domain):
            async with semaphore:
                try:
                    return await analyze_domain(domain, session)
                except Exception as e:
                    logger.error(f"Error analyzing domain {domain}: {e}")
                    return {"domain_name": domain, "error": str(e), "total_snapshots": 0, "recommended": False, "is_long_live": False}
        
        try:
            async with aiohttp.ClientSession() as session:
                tasks = [analyze_with_semaphore(domain) for domain in batch_domains]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Error creating aiohttp session for batch {i//batch_size + 1}: {e}")
            continue
        
        # Обработка результатов с исключениями
        for j, result in enumerate(batch_results):
            if isinstance(result, Exception):
                logger.error(f"Error analyzing domain {batch_domains[j]}: {result}")
                all_results.append({
                    "domain_name": batch_domains[j],
                    "error": str(result),
                    "total_snapshots": 0,
                    "recommended": False,
                    "is_long_live": False
                })
            else:
                all_results.append(result)
    
    return all_results
