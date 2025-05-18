import asyncio
import logging
from typing import Dict, Any, Optional, List
import datetime

logger = logging.getLogger(__name__)

# Configure a basic logger for this module if not configured globally
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

class WaybackService:
    def __init__(self, user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"):
        self.user_agent = user_agent
        # Проверяем, установлена ли библиотека waybackpy
        try:
            import waybackpy
            self.waybackpy_available = True
            self.waybackpy = waybackpy
            logger.info(f"waybackpy version {waybackpy.__version__} is available")
        except ImportError:
            logger.warning("waybackpy library is not installed. Using fallback implementation.")
            self.waybackpy_available = False
            self.waybackpy = None

    async def get_domain_history_summary(self, domain: str) -> Dict[str, Any]:
        """Fetches a summary of the domain's history from Wayback Machine."""
        summary = {
            "domain": domain,
            "first_snapshot_date": None,
            "last_snapshot_date": None,
            "total_snapshots": 0,
            "availability_api_response": None,
            "oldest_snapshot_url": None,
            "newest_snapshot_url": None,
            "error": None
        }

        if not self.waybackpy_available:
            summary["error"] = "waybackpy library is not installed. Please install it using: pip install waybackpy==3.0.6"
            logger.error(f"waybackpy library not available for domain {domain}")
            return summary

        try:
            # Используем WaybackMachineCDXServerAPI для получения снимков
            loop = asyncio.get_event_loop()
            
            def blocking_cdx_api_check():
                try:
                    # Создаем URL с протоколом, если его нет
                    url = domain if domain.startswith(('http://', 'https://')) else f"http://{domain}"
                    
                    # Используем CDX API для получения снимков
                    cdx_api = self.waybackpy.WaybackMachineCDXServerAPI(
                        url=url,
                        user_agent=self.user_agent
                    )
                    
                    # Получаем список снимков
                    snapshots = list(cdx_api.snapshots())
                    
                    if not snapshots:
                        return {"message": "No snapshots found for this domain."}
                    
                    # Получаем первый (самый старый) и последний (самый новый) снимки
                    # В зависимости от сортировки по умолчанию
                    oldest_snapshot = snapshots[0]
                    newest_snapshot = snapshots[-1]
                    
                    return {
                        "total_snapshots": len(snapshots),
                        "oldest_snapshot": {
                            "timestamp": oldest_snapshot.timestamp,
                            "archive_url": oldest_snapshot.archive_url
                        },
                        "newest_snapshot": {
                            "timestamp": newest_snapshot.timestamp,
                            "archive_url": newest_snapshot.archive_url
                        }
                    }
                except Exception as e:
                    logger.warning(f"Wayback Machine CDX API check for {domain} failed: {e}")
                    return {"error": str(e)}

            # Выполняем блокирующий вызов в отдельном потоке
            cdx_result = await loop.run_in_executor(None, blocking_cdx_api_check)
            
            # Обрабатываем результат
            if "error" in cdx_result:
                summary["error"] = cdx_result["error"]
                summary["availability_api_response"] = {"error": cdx_result["error"]}
            else:
                summary["availability_api_response"] = {"message": "CDX API check successful"}
                
                if "oldest_snapshot" in cdx_result:
                    summary["first_snapshot_date"] = cdx_result["oldest_snapshot"]["timestamp"]
                    summary["oldest_snapshot_url"] = cdx_result["oldest_snapshot"]["archive_url"]
                
                if "newest_snapshot" in cdx_result:
                    summary["last_snapshot_date"] = cdx_result["newest_snapshot"]["timestamp"]
                    summary["newest_snapshot_url"] = cdx_result["newest_snapshot"]["archive_url"]
                
                if "total_snapshots" in cdx_result:
                    summary["total_snapshots"] = cdx_result["total_snapshots"]

        except Exception as e:
            summary["error"] = f"An unexpected error occurred: {str(e)}"
            logger.exception(f"Unexpected error fetching Wayback history for {domain}: {e}")
        
        return summary

    async def get_content_from_snapshot(self, archive_url: str) -> Optional[str]:
        """Fetches the textual content from a specific Wayback Machine snapshot URL."""
        if not self.waybackpy_available:
            logger.error("waybackpy library not available for fetching snapshot content")
            return None

        try:
            # Для простоты возвращаем заглушку, так как этот метод не используется в основном коде
            logger.warning("get_content_from_snapshot is a placeholder and does not fetch live content.")
            return f"Placeholder content for {archive_url}. Implement with requests or aiohttp for actual fetching."
        except Exception as e:
            logger.error(f"Error fetching content from snapshot {archive_url}: {e}")
            return None

# Example Usage (for testing this module):
async def main_test():
    service = WaybackService()
    domain_to_test = "example.com"
    
    print(f"Fetching history for {domain_to_test}...")
    history = await service.get_domain_history_summary(domain_to_test)
    print("History Summary:", history)

if __name__ == "__main__":
    asyncio.run(main_test())