import logging
from fastapi import APIRouter, Depends
from api.v1.schemas.library import LibraryResponse
from core.dependencies import get_library_service
from services.library_service import LibraryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/library", tags=["library"])


@router.get("/", response_model=LibraryResponse)
async def get_library(
    library_service: LibraryService = Depends(get_library_service)
):
    library = await library_service.get_library()
    return LibraryResponse(library=library)


@router.get("/artists")
async def get_library_grouped(
    library_service: LibraryService = Depends(get_library_service)
):
    grouped = await library_service.get_library_grouped()
    return {"library": grouped}
