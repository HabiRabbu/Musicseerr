from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_frontend(app: FastAPI):
    static_dir = Path(__file__).parent / "static"
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    @app.get("/")
    def serve_root():
        index = static_dir / "index.html"
        if index.exists():
            return FileResponse(index)
        return {"detail": "Frontend not built yet"}
