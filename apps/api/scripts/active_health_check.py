import asyncio
import logging
import time

from services.providers import PROVIDERS
from services.health_metrics import record_provider_health
from services.transport import shared_transport

logger = logging.getLogger(__name__)

async def run_active_health_check():
    """
    Actively pings each provider's homepage or search page to record health metrics.
    """
    logger.info("Starting active provider health check...")
    
    async def check_provider(provider_id: str, provider_proxy):
        start_time = time.time()
        is_reachable = False
        try:
            # We'll just try to do a basic search or hit the homepage 
            # We can use the underlying provider's get_search_results or similar if available,
            # or just do a raw request to its base URL via the transport.
            base_url = getattr(provider_proxy.provider, 'base_url', None)
            
            if base_url:
                html = await shared_transport.get_html(base_url)
                if html and len(html) > 100:
                    is_reachable = True
            else:
                # Fallback: try a dummy search
                results = await provider_proxy.get_search_results("naruto")
                is_reachable = isinstance(results, list)
                
            response_ms = (time.time() - start_time) * 1000
            await record_provider_health(provider_id, is_reachable, response_ms)
            logger.info(f"Health check {provider_id}: {'OK' if is_reachable else 'FAIL'} ({response_ms:.2f}ms)")
        except Exception as e:
            response_ms = (time.time() - start_time) * 1000
            await record_provider_health(provider_id, False, response_ms)
            logger.warning(f"Health check {provider_id}: FAIL ({response_ms:.2f}ms) - {e}")

    tasks = []
    from services.pipeline import PROVIDERS
    
    for pid, proxy in PROVIDERS.items():
        tasks.append(check_provider(pid, proxy))
        
    await asyncio.gather(*tasks)
    logger.info("Active health check completed.")

if __name__ == "__main__":
    asyncio.run(run_active_health_check())
