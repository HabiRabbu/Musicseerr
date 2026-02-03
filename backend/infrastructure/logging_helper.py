import logging
from typing import Optional

logger = logging.getLogger(__name__)


def format_mbid(mbid: str) -> str:
    return f"{mbid[:8]}..." if len(mbid) >= 8 else mbid


def log_cache_hit(entity_type: str, mbid: str, source: Optional[str] = None) -> None:
    source_info = f" from {source}" if source else ""
    logger.info(f"Cache hit: {entity_type} {format_mbid(mbid)}{source_info}")


def log_cache_miss(entity_type: str, mbid: str, source: Optional[str] = None) -> None:
    source_info = f" in {source}" if source else ""
    logger.debug(f"Cache miss: {entity_type} {format_mbid(mbid)}{source_info}")


def log_fetch_start(entity_type: str, mbid: str, source: str) -> None:
    logger.info(f"Fetching {entity_type} {format_mbid(mbid)} from {source}")


def log_fetch_success(entity_type: str, mbid: str, source: str) -> None:
    logger.info(f"Fetch success: {entity_type} {format_mbid(mbid)} from {source}")


def log_fetch_failed(entity_type: str, mbid: str, source: str, reason: Optional[str] = None) -> None:
    reason_info = f": {reason}" if reason else ""
    logger.warning(f"Fetch failed: {entity_type} {format_mbid(mbid)} from {source}{reason_info}")


def log_image_fetch(action: str, entity_type: str, mbid: str, source: str) -> None:
    logger.info(f"Image {action}: {entity_type} {format_mbid(mbid)} from {source}")


def log_http_error(entity_type: str, mbid: str, source: str, status_code: int) -> None:
    logger.warning(f"HTTP {status_code}: {entity_type} {format_mbid(mbid)} from {source}")


def log_exception(entity_type: str, mbid: str, operation: str, error: Exception) -> None:
    logger.error(f"Exception in {operation} for {entity_type} {format_mbid(mbid)}: {error}")
