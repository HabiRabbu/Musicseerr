"""Lightweight Emby authentication helper.

Only handles credential validation — not a full media-source repository.
"""
import logging

import httpx

logger = logging.getLogger(__name__)

_DEVICE_AUTH = (
    'MediaBrowser Client="Musicseerr", Device="Server", '
    'DeviceId="musicseerr-server", Version="1.0"'
)


async def emby_authenticate(url: str, username: str, password: str) -> dict | None:
    """Validate Emby credentials and return user info, or None on failure.

    Returns dict with keys: username, user_id, is_admin.
    """
    base = url.rstrip("/")
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
        try:
            response = await client.post(
                f"{base}/Users/AuthenticateByName",
                json={"Username": username, "Pw": password},
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-Emby-Authorization": _DEVICE_AUTH,
                },
            )
            if response.status_code in (401, 403):
                return None
            if response.status_code != 200:
                logger.warning("Emby auth returned status %d", response.status_code)
                return None
            data = response.json()
            user_obj = data.get("User", {})
            return {
                "username": user_obj.get("Name", username),
                "user_id": user_obj.get("Id", ""),
                "is_admin": user_obj.get("Policy", {}).get("IsAdministrator", False),
            }
        except httpx.TimeoutException:
            logger.warning("Emby auth timed out for user %s", username)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("Emby auth error: %s", exc)
            return None


async def emby_verify_server(url: str) -> tuple[bool, str]:
    """Check whether the Emby server at *url* is reachable.

    Returns (True, server_name) or (False, error_message).
    """
    base = url.rstrip("/")
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
        try:
            response = await client.get(
                f"{base}/System/Info/Public",
                headers={"Accept": "application/json"},
            )
            if response.status_code == 200:
                data = response.json()
                name = data.get("ServerName") or data.get("ProductName") or "Emby"
                return True, name
            return False, f"Server returned status {response.status_code}"
        except httpx.TimeoutException:
            return False, "Connection timed out"
        except Exception as exc:  # noqa: BLE001
            return False, f"Could not reach server: {exc}"
