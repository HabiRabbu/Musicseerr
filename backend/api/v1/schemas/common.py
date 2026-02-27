from typing import Literal, Optional
from pydantic import BaseModel, Field


class SuccessResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    details: Optional[str] = None


class ServiceStatus(BaseModel):
    status: Literal["ok", "error"]
    version: Optional[str] = None
    message: Optional[str] = None


class StatusReport(BaseModel):
    status: Literal["ok", "degraded", "error"]
    services: dict[str, ServiceStatus]


class LastFmTagSchema(BaseModel):
    name: str
    url: Optional[str] = None
