import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from core.dependencies import get_request_queue, get_cache, init_app_state, cleanup_app_state
from core.tasks import start_cache_cleanup_task
from core.exceptions import ResourceNotFoundError, ExternalServiceError
from core.exception_handlers import (
    resource_not_found_handler,
    external_service_error_handler,
    circuit_open_error_handler,
    general_exception_handler
)
from infrastructure.resilience.retry import CircuitOpenError
from middleware import PerformanceMiddleware
from static_server import mount_frontend
from api.v1.routes import (
    search, requests, library, status, queue, covers, artists, albums, settings
)
from api.v1.routes import cache as cache_routes

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown."""
    logger.info("Starting Musicseerr...")
    
    await init_app_state(app)
    
    cache = get_cache()
    start_cache_cleanup_task(cache)

    request_queue = get_request_queue()
    await request_queue.start()
    
    logger.info("Musicseerr started successfully")
    
    yield

    logger.info("Shutting down Musicseerr...")

    await request_queue.stop()

    await cleanup_app_state()
    
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
app.include_router(cache_routes.router)

mount_frontend(app)
