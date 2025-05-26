"""
Модуль для анализа доменов через Wayback Machine API.
Адаптирован из way2_fixed.py для использования в FastAPI сервисе.
"""
import asyncio
import json
import logging
import statistics
from datetime import datetime

import aiohttp

# Конфигурация
CDX_API = "https://web.archive.org/cdx/search/cdx"
AVAIL_API = "https://archive.org/wayback/available"
TIMEMAP_URL = "http://web.archive.org/web/timemap/link/{url}"
REQUEST_TIMEOUT = 30  # секунд
RETRY_DELAY = 2  # секунд
RETRY_COUNT = 3
DEFAULT_CONCURRENCY = 5  # Ограничение на количество одновременных запросов

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
    avail_params = {"url": domain}
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
    tm_text = await safe_request(session, "GET", TIMEMAP_URL.format(url=domain))
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
                for k in ("first_snapshot", "last_snapshot", "avg_interval_days",
                          "max_gap_days", "years_covered", "snapshots_per_year", "unique_versions"):
                    info[k] = None
        except Exception as e:
            logger.error(f"Error processing snapshot metrics for {domain}: {e}. Records: {records[:5]}")
            for k in ("first_snapshot", "last_snapshot", "avg_interval_days",
                      "max_gap_days", "years_covered", "snapshots_per_year", "unique_versions"):
                info[k] = None
    else:
        for k in ("first_snapshot", "last_snapshot", "avg_interval_days",
                  "max_gap_days", "years_covered", "snapshots_per_year", "unique_versions"):
            info[k] = None

    # Флаги
    total_snapshots_val = info.get("total_snapshots", 0)
    max_gap_days_val = info.get("max_gap_days")
    avg_interval_days_val = info.get("avg_interval_days")

    info["is_good"] = (total_snapshots_val >= 1) and (max_gap_days_val is not None and max_gap_days_val < 365)
    info["recommended"] = (total_snapshots_val >= 200) and (avg_interval_days_val is not None and avg_interval_days_val < 30)
    
    # Добавляем оценку и описание для совместимости с frontend
    if info["recommended"]:
        info["assessment_score"] = 8.5
        info["assessment_summary"] = f"Домен {domain} имеет хорошую историю в архиве."
    elif info["is_good"]:
        info["assessment_score"] = 6.5
        info["assessment_summary"] = f"Домен {domain} имеет среднюю историю в архиве."
    else:
        info["assessment_score"] = 4.0
        info["assessment_summary"] = f"Домен {domain} имеет недостаточную историю в архиве."

    info["analysis_time_sec"] = round((datetime.utcnow() - start).total_seconds(), 2)
    return info


async def analyze_domains(domains: list, concurrency: int = DEFAULT_CONCURRENCY) -> list:
    """Анализ списка доменов с ограничением параллелизма."""
    if not domains:
        logger.warning("No domains provided for analysis.")
        return []

    semaphore = asyncio.Semaphore(concurrency)
    conn = aiohttp.TCPConnector(limit_per_host=concurrency)
    
    async def analyze_with_semaphore(domain, session):
        async with semaphore:
            return await analyze_domain(domain, session)
    
    # Создаем одну общую сессию для всех доменов
    async with aiohttp.ClientSession(connector=conn) as session:
        tasks = [asyncio.create_task(analyze_with_semaphore(domain, session)) for domain in domains]
        results = []
        
        for fut in asyncio.as_completed(tasks):
            try:
                result = await fut
                if result:
                    results.append(result)
                else:
                    logger.error("Task for a domain completed but returned None.")
            except Exception as e:
                logger.error(f"Error processing a domain task: {e}")
    
    return results
