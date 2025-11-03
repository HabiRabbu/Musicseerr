from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from config_manager import CONFIG
from static_server import mount_frontend
from http_client import aclose
from utils import request_queue
from utils.cache import start_cache_cleanup_task
from middleware import PerformanceMiddleware

from routes import search, requests, library, status, queue, covers, artist

app = FastAPI(
    title="Musicseerr",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(PerformanceMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=6)

@app.get("/health")
def read_health():
    return {
        "status": "ok",
        "message": "Musicseerr backend running",
        "config_loaded": CONFIG is not None,
    }

app.include_router(search.router)
app.include_router(requests.router)
app.include_router(library.router)
app.include_router(queue.router)
app.include_router(status.router)
app.include_router(covers.router)
app.include_router(artist.router)

mount_frontend(app)


@app.on_event("startup")
async def startup_event():
    request_queue.start_processor()
    start_cache_cleanup_task()


@app.on_event("shutdown")
async def shutdown_event():
    await request_queue.stop_processor()
    await aclose()
