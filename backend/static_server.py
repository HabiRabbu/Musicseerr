from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_frontend(app: FastAPI):
    static_dir = Path(__file__).parent / "static"
    build_dir = static_dir
    index_html = build_dir / "index.html"

    # Mount static files (JS, CSS, images, etc.) at /_app
    if (build_dir / "_app").exists():
        app.mount("/_app", StaticFiles(directory=build_dir / "_app"), name="_app")

    # Serve specific static files
    @app.get("/robots.txt")
    async def serve_robots():
        robots = build_dir / "robots.txt"
        if robots.exists():
            return FileResponse(robots)
        return {"detail": "Not found"}

    @app.get("/logo.png")
    async def serve_logo():
        logo = build_dir / "logo.png"
        if logo.exists():
            return FileResponse(logo)
        return {"detail": "Not found"}

    @app.get("/logo_wide.png")
    async def serve_logo_wide():
        logo_wide = build_dir / "logo_wide.png"
        if logo_wide.exists():
            return FileResponse(logo_wide)
        return {"detail": "Not found"}

    # Root path
    @app.get("/")
    async def serve_root():
        if index_html.exists():
            return FileResponse(index_html)
        return {"detail": "Frontend not built yet"}

    # Catch-all for SPA routes (must be last)
    # This handles all non-API routes like /search, /library, etc.
    @app.get("/{full_path:path}")
    async def serve_spa_routes(full_path: str):
        # Don't interfere with API routes
        if full_path.startswith("api"):
            return {"detail": "API route not found"}
        
        # For all other routes, serve index.html for client-side routing
        if index_html.exists():
            return FileResponse(index_html)
        return {"detail": "Frontend not built yet"}
