import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from core.dependencies import (
    get_request_queue, 
    get_cache, 
    get_library_service,
    get_preferences_service,
    init_app_state, 
    cleanup_app_state
)
from core.tasks import start_cache_cleanup_task, start_library_sync_task, start_disk_cache_cleanup_task, start_home_cache_warming_task, start_discover_cache_warming_task
from core.exceptions import ResourceNotFoundError, ExternalServiceError, ValidationError
from core.exception_handlers import (
    resource_not_found_handler,
    external_service_error_handler,
    circuit_open_error_handler,
    validation_error_handler,
    general_exception_handler
)
from infrastructure.resilience.retry import CircuitOpenError
from middleware import PerformanceMiddleware
from static_server import mount_frontend
from api.v1.routes import (
    search, requests, library, status, queue, covers, artists, albums, settings, home, discover
)
from api.v1.routes import cache as cache_routes
from api.v1.routes import cache_status as cache_status_routes
from api.v1.routes import youtube as youtube_routes

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Musicseerr...")
    
    await init_app_state(app)
    
    preferences_service = get_preferences_service()
    advanced_settings = preferences_service.get_advanced_settings()

    cache = get_cache()
    start_cache_cleanup_task(cache, interval=advanced_settings.memory_cache_cleanup_interval)
    
    from core.dependencies import get_disk_cache
    disk_cache = get_disk_cache()
    start_disk_cache_cleanup_task(disk_cache, interval=advanced_settings.disk_cache_cleanup_interval)
    
    library_service = get_library_service()
    start_library_sync_task(library_service, preferences_service)

    request_queue = get_request_queue()
    await request_queue.start()
    
    from core.tasks import warm_library_cache
    from core.dependencies import get_album_service, get_library_cache
    
    def handle_cache_warming_error(task: asyncio.Task):
        try:
            if task.cancelled():
                logger.info("Cache warming was cancelled")
                return
            
            exc = task.exception()
            if exc:
                logger.error(f"Cache warming failed: {exc}", exc_info=exc)
        except asyncio.CancelledError:
            logger.info("Cache warming was cancelled")
        except Exception as e:
            logger.error(f"Error checking cache warming task: {e}")
    
    cache_task = asyncio.create_task(
        warm_library_cache(library_service, get_album_service(), get_library_cache())
    )
    cache_task.add_done_callback(handle_cache_warming_error)

    from services.cache_status_service import CacheStatusService
    library_cache = get_library_cache()
    status_service = CacheStatusService(library_cache)

    interrupted_state = await status_service.restore_from_persistence()
    if interrupted_state:
        logger.info("Found interrupted library sync, scheduling resume...")

        async def resume_sync():
            try:
                await asyncio.sleep(5)
                artists = await library_cache.get_artists()
                albums = await library_cache.get_albums()
                if artists or albums:
                    artists_dicts = [{'mbid': a['mbid'], 'name': a['name']} for a in artists]
                    await library_service._precache_service.precache_library_resources(
                        artists_dicts, albums, resume=True
                    )
                else:
                    logger.warning("No cached artists/albums to resume sync with, clearing state")
                    await library_cache.clear_sync_state()
            except Exception as e:
                logger.error(f"Failed to resume interrupted sync: {e}")
                await status_service.complete_sync(str(e))

        resume_task = asyncio.create_task(resume_sync())
        resume_task.add_done_callback(lambda t: logger.info("Resume sync task completed") if not t.exception() else logger.error(f"Resume sync failed: {t.exception()}"))

    from core.dependencies import get_home_service
    start_home_cache_warming_task(get_home_service())

    from core.dependencies import get_discover_service
    start_discover_cache_warming_task(get_discover_service())
    
    logger.info("Musicseerr started successfully")
    
    try:
        yield
    finally:
        logger.info("Shutting down Musicseerr...")

        try:
            await request_queue.stop()
        except Exception as e:
            logger.error(f"Error stopping request queue: {e}")

        try:
            await cleanup_app_state()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        
        logger.info("Musicseerr shut down successfully")


app = FastAPI(
    title="Musicseerr",
    description="Music request and management system",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

app.add_exception_handler(ResourceNotFoundError, resource_not_found_handler)
app.add_exception_handler(ExternalServiceError, external_service_error_handler)
app.add_exception_handler(ValidationError, validation_error_handler)
app.add_exception_handler(CircuitOpenError, circuit_open_error_handler)
app.add_exception_handler(Exception, general_exception_handler)

app.add_middleware(PerformanceMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=6)


@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Musicseerr backend running"}


app.include_router(search.router)
app.include_router(requests.router)
app.include_router(library.router)
app.include_router(queue.router)
app.include_router(status.router)
app.include_router(covers.router)
app.include_router(artists.router)
app.include_router(albums.router)
app.include_router(settings.router)
app.include_router(home.router)
app.include_router(discover.router)
app.include_router(youtube_routes.router)
app.include_router(cache_routes.router)
app.include_router(cache_status_routes.router)

mount_frontend(app)
