from datetime import datetime
from typing import Optional


_FAILED_STATES = {"downloadFailed", "downloadFailedPending", "importFailed"}
_IMPORT_BLOCKED_STATES = {"importBlocked", "importPending"}

_DOWNLOAD_STATE_MAP: dict[str, str] = {
    "importing": "importing",
    "imported": "imported",
}


def resolve_display_status(download_state: Optional[str]) -> str:
    if download_state in _FAILED_STATES:
        return "importFailed"
    if download_state in _IMPORT_BLOCKED_STATES:
        return "importBlocked"
    return _DOWNLOAD_STATE_MAP.get(download_state or "", "pending")


def parse_eta(eta_str: Optional[str]) -> Optional[datetime]:
    if not eta_str:
        return None
    try:
        return datetime.fromisoformat(eta_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def extract_cover_url(album_data: dict) -> Optional[str]:
    images = album_data.get("images", [])
    for img in images:
        if img.get("coverType", "").lower() == "cover":
            return img.get("remoteUrl") or img.get("url")
    if images:
        return images[0].get("remoteUrl") or images[0].get("url")
    return None
