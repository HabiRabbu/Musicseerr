from fastapi import FastAPI
from config_manager import CONFIG
from static_server import mount_frontend

app = FastAPI(title="Musicseerr")
mount_frontend(app)

# Example route
@app.get("/api/status")
def read_status():
    return {
        "status": "ok",
        "message": "Musicseerr backend running",
        "config_loaded": CONFIG is not None
    }
