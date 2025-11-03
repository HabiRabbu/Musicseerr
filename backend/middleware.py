import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class PerformanceMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        response = await call_next(request)
        process_time = time.perf_counter() - start_time
        response.headers["X-Response-Time"] = f"{process_time:.3f}s"
        
        if process_time > 1.0:
            print(f"SLOW REQUEST: {request.method} {request.url.path} took {process_time:.2f}s")
        
        return response
