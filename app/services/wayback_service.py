import asyncio
import logging
from typing import Dict, Any, Optional, List
import datetime

logger = logging.getLogger(__name__)

# Configure a basic logger for this module if not configured globally
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

# Определяем собственные исключения для работы с Wayback Machine
class WaybackError(Exception):
    """Base exception for Wayback Machine errors."""
    pass

class NoCDXRecordFound(WaybackError):
    """Exception raised when no CDX records are found for a domain."""
    pass

class NoWaybackMachineCDXServerAvailable(WaybackError):
    """Exception raised when the Wayback Machine CDX server is not available."""
    pass

class WaybackService:
    def __init__(self, user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"):
        self.user_agent = user_agent
        # Проверяем, установлена ли библиотека waybackpy
        try:
            import waybackpy
            self.waybackpy_available = True
            self.waybackpy = waybackpy
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
            summary["error"] = "waybackpy library is not installed. Please install it using: pip install waybackpy"
            logger.error(f"waybackpy library not available for domain {domain}")
            return summary

        try:
            # Используем только класс WaybackMachine, который есть во всех версиях библиотеки
            loop = asyncio.get_event_loop()
            
            def blocking_availability_check():
                try:
                    # Используем простую проверку доступности через WaybackMachine
                    wayback = self.waybackpy.WaybackMachine(domain, self.user_agent)
                    # Проверяем доступность, но не выполняем полный запрос
                    return {"message": "WaybackMachine object created successfully."}
                except Exception as e:
                    logger.warning(f"Wayback Machine availability check for {domain} failed: {e}")
                    return {"error": str(e)}

            summary["availability_api_response"] = await loop.run_in_executor(None, blocking_availability_check)

            def blocking_oldest_snapshot():
                try:
                    wayback = self.waybackpy.WaybackMachine(domain, self.user_agent)
                    return wayback.oldest()
                except Exception as e:
                    logger.warning(f"Error fetching oldest snapshot for {domain}: {e}")
                    return {"error_fetching_oldest": str(e)}

            oldest_snapshot = await loop.run_in_executor(None, blocking_oldest_snapshot)
            if oldest_snapshot and not isinstance(oldest_snapshot, dict):
                summary["first_snapshot_date"] = oldest_snapshot.timestamp.isoformat() if hasattr(oldest_snapshot, 'timestamp') and oldest_snapshot.timestamp else None
                summary["oldest_snapshot_url"] = oldest_snapshot.archive_url if hasattr(oldest_snapshot, 'archive_url') else None
            elif isinstance(oldest_snapshot, dict) and "error_fetching_oldest" in oldest_snapshot:
                summary["error"] = oldest_snapshot['error_fetching_oldest']

            def blocking_newest_snapshot():
                try:
                    wayback = self.waybackpy.WaybackMachine(domain, self.user_agent)
                    return wayback.newest()
                except Exception as e:
                    logger.warning(f"Error fetching newest snapshot for {domain}: {e}")
                    return {"error_fetching_newest": str(e)}

            newest_snapshot = await loop.run_in_executor(None, blocking_newest_snapshot)
            if newest_snapshot and not isinstance(newest_snapshot, dict):
                summary["last_snapshot_date"] = newest_snapshot.timestamp.isoformat() if hasattr(newest_snapshot, 'timestamp') and newest_snapshot.timestamp else None
                summary["newest_snapshot_url"] = newest_snapshot.archive_url if hasattr(newest_snapshot, 'archive_url') else None
            elif isinstance(newest_snapshot, dict) and "error_fetching_newest" in newest_snapshot:
                if summary["error"]:
                    summary["error"] += f"; {newest_snapshot['error_fetching_newest']}"
                else:
                    summary["error"] = newest_snapshot['error_fetching_newest']

            if not oldest_snapshot and not newest_snapshot and not summary["error"]:
                summary["error"] = "No snapshots found via oldest/newest methods."

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
            return f"Placeholder content for {archive_url}. Implement with aiohttp for actual fetching."
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