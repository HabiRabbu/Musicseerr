from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_frontend(app: FastAPI):
    backend_static = Path(__file__).parent / "static"
    frontend_root = Path(__file__).resolve().parents[1] / "frontend"
    build_candidates = [
        backend_static,
        frontend_root / "build",
    ]

    def first_existing_build() -> Path:
        for candidate in build_candidates:
            index_file = candidate / "index.html"
            if index_file.exists():
                return candidate
        return backend_static

    build_dir = first_existing_build()
    index_html = build_dir / "index.html"
    asset_dirs = [
        build_dir,
        frontend_root / "static",
    ]

    def resolve_asset(filename: str) -> Optional[Path]:
        for directory in asset_dirs:
            candidate = directory / filename
            if candidate.exists():
                return candidate
        return None

    if (build_dir / "_app").exists():
        app.mount("/_app", StaticFiles(directory=build_dir / "_app"), name="_app")

    img_dir = build_dir / "img"
    if img_dir.exists():
        app.mount("/img", StaticFiles(directory=img_dir), name="img")

    @app.get("/robots.txt")
    async def serve_robots():
        robots = resolve_asset("robots.txt")
        if robots:
            return FileResponse(robots)
        raise HTTPException(status_code=404, detail="Not found")

    @app.get("/logo.png")
    async def serve_logo():
        logo = resolve_asset("logo.png")
        if logo:
            return FileResponse(logo)
        raise HTTPException(status_code=404, detail="Not found")

    @app.get("/logo_wide.png")
    async def serve_logo_wide():
        logo_wide = resolve_asset("logo_wide.png")
        if logo_wide:
            return FileResponse(logo_wide)
        raise HTTPException(status_code=404, detail="Not found")

    @app.get("/")
    async def serve_root():
        if index_html.exists():
            return FileResponse(index_html)
        raise HTTPException(status_code=404, detail="Frontend not built yet")

    @app.get("/{full_path:path}")
    async def serve_spa_routes(full_path: str):
        if full_path.startswith("api"):
            raise HTTPException(status_code=404, detail="API route not found")

        if index_html.exists():
            return FileResponse(index_html)
        raise HTTPException(status_code=404, detail="Frontend not built yet")
