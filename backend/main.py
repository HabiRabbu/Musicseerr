from fastapi import FastAPI
from config_manager import CONFIG
from static_server import mount_frontend
from http_client import aclose

from routes import search, requests, library, status, queue, covers

app = FastAPI(title="Musicseerr")

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

mount_frontend(app)


@app.on_event("shutdown")
async def shutdown_event():
    await aclose()
