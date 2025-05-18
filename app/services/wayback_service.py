import asyncio
import waybackpy
from waybackpy.exceptions import WaybackError, NoCDXRecordFound
from typing import Dict, Any, Optional, List
import datetime
import logging

logger = logging.getLogger(__name__)

# Configure a basic logger for this module if not configured globally
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

# Определяем исключение, если оно отсутствует в библиотеке
class NoWaybackMachineCDXServerAvailable(WaybackError):
    """Exception raised when the Wayback Machine CDX server is not available."""
    pass

class WaybackService:
    def __init__(self, user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"):
        self.user_agent = user_agent

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
        try:
            # Use a timeout for the WaybackMachine constructor if possible, or handle it in the calls
            # wayback = waybackpy.WaybackMachine(domain, self.user_agent)
            # The library itself doesn't seem to support async for the main WaybackMachine object initialization directly
            # or for all its methods. We'll use it synchronously within an async executor if needed,
            # or use its async-compatible parts if available.
            # For now, let's assume some parts can be called directly or wrapped.

            # The library's own `near` and `oldest` methods are blocking.
            # We should use asyncio.to_thread for blocking calls.

            loop = asyncio.get_event_loop()
            
            def blocking_availability_check():
                try:
                    # The availability API is often rate-limited or unreliable.
                    # return waybackpy.WaybackMachine(domain, self.user_agent).availability()
                    # The above line creates a new object each time, which is inefficient.
                    # Let's try to get CDX records first as a proxy for availability and count.
                    cdx = waybackpy.WaybackMachineCDX(domain, self.user_agent)
                    # Get total snapshots count (can be slow for large sites)
                    # For a summary, we might not need the full count if it's too slow.
                    # Let's try to get the oldest and newest snapshots first.
                    return {"message": "CDX object created, specific availability check deferred or done via snapshots."}
                except Exception as e:
                    logger.warning(f"Wayback Machine availability check for {domain} failed: {e}")
                    return {"error": str(e)}

            summary["availability_api_response"] = await loop.run_in_executor(None, blocking_availability_check)

            def blocking_oldest_snapshot():
                try:
                    return waybackpy.WaybackMachine(domain, self.user_agent).oldest()
                except NoCDXRecordFound:
                    return None
                except Exception as e:
                    logger.warning(f"Error fetching oldest snapshot for {domain}: {e}")
                    return {"error_fetching_oldest": str(e)}

            oldest_snapshot = await loop.run_in_executor(None, blocking_oldest_snapshot)
            if oldest_snapshot and not isinstance(oldest_snapshot, dict):
                summary["first_snapshot_date"] = oldest_snapshot.timestamp.isoformat() if oldest_snapshot.timestamp else None
                summary["oldest_snapshot_url"] = oldest_snapshot.archive_url
            elif isinstance(oldest_snapshot, dict) and "error_fetching_oldest" in oldest_snapshot:
                 summary["error"] = summary.get("error", "") + f"; Oldest: {oldest_snapshot['error_fetching_oldest']}"

            def blocking_newest_snapshot():
                try:
                    return waybackpy.WaybackMachine(domain, self.user_agent).newest()
                except NoCDXRecordFound:
                    return None
                except Exception as e:
                    logger.warning(f"Error fetching newest snapshot for {domain}: {e}")
                    return {"error_fetching_newest": str(e)}

            newest_snapshot = await loop.run_in_executor(None, blocking_newest_snapshot)
            if newest_snapshot and not isinstance(newest_snapshot, dict):
                summary["last_snapshot_date"] = newest_snapshot.timestamp.isoformat() if newest_snapshot.timestamp else None
                summary["newest_snapshot_url"] = newest_snapshot.archive_url
            elif isinstance(newest_snapshot, dict) and "error_fetching_newest" in newest_snapshot:
                summary["error"] = summary.get("error", "") + f"; Newest: {newest_snapshot['error_fetching_newest']}"

            # Getting total snapshots can be very slow. For a summary, this might be an overkill.
            # Consider if this is truly needed for the initial summary or can be a separate detailed call.
            # For now, we'll skip the full count to keep the summary faster.
            # summary["total_snapshots"] = len(list(wayback.snapshots())) # This is blocking and potentially huge

            if not oldest_snapshot and not newest_snapshot and not summary["error"]:
                 summary["error"] = "No snapshots found via oldest/newest methods."

        except NoCDXRecordFound:
            summary["error"] = "No CDX records found for this domain."
            logger.info(f"No CDX records for {domain}")
        except NoWaybackMachineCDXServerAvailable:
            summary["error"] = "Wayback Machine CDX server is not available."
            logger.error(f"Wayback Machine CDX server unavailable for {domain}")
        except WaybackError as e:
            summary["error"] = f"A Wayback Machine specific error occurred: {str(e)}"
            logger.error(f"WaybackError for {domain}: {e}")
        except Exception as e:
            summary["error"] = f"An unexpected error occurred: {str(e)}"
            logger.exception(f"Unexpected error fetching Wayback history for {domain}: {e}")
        
        return summary

    async def get_content_from_snapshot(self, archive_url: str) -> Optional[str]:
        """Fetches the textual content from a specific Wayback Machine snapshot URL."""
        # waybackpy.Snapshot.get() is blocking. We need to wrap it.
        try:
            loop = asyncio.get_event_loop()
            
            def blocking_get_content():
                # This requires creating a Snapshot object first, which might not be straightforward
                # just from an archive_url without knowing the original URL and timestamp.
                # The library's `get()` method on a snapshot object fetches content.
                # However, waybackpy itself doesn't provide a direct way to get a Snapshot object from an archive_url.
                # A more robust way would be to use an HTTP client like aiohttp to fetch the content directly.
                # For now, this is a placeholder as waybackpy's direct support for this is limited.
                # A better approach: use an HTTP client to fetch and parse the archive_url.
                # For simplicity, this function will remain a placeholder for now.
                # snapshot = waybackpy.WaybackMachine(domain, self.user_agent).newest() # Example
                # return snapshot.get() # This is blocking
                logger.warning("get_content_from_snapshot is a placeholder and does not fetch live content yet.")
                return f"Simulated content for {archive_url}"
            
            # content = await loop.run_in_executor(None, blocking_get_content)
            # return content
            logger.warning("get_content_from_snapshot using aiohttp is preferred but not implemented here yet.")
            return f"Placeholder content for {archive_url}. Implement with aiohttp for actual fetching."
        except Exception as e:
            logger.error(f"Error fetching content from snapshot {archive_url}: {e}")
            return None

# Example Usage (for testing this module):
async def main_test():
    service = WaybackService()
    # domain_to_test = "google.com"
    domain_to_test = "nonexistentdomain1234567890qwerty.com"
    # domain_to_test = "example.com"
    
    print(f"Fetching history for {domain_to_test}...")
    history = await service.get_domain_history_summary(domain_to_test)
    print("History Summary:", history)

    if history.get("newest_snapshot_url"):
        print(f"\nFetching content from newest snapshot: {history['newest_snapshot_url']}...")
        content = await service.get_content_from_snapshot(history['newest_snapshot_url'])
        print("Snapshot Content (Placeholder):", content[:200] if content else "No content")

if __name__ == "__main__":
    asyncio.run(main_test())