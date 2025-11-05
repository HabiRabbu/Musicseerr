import httpx
import logging
from typing import Optional
from core.config import Settings

logger = logging.getLogger(__name__)

USER_AGENT = "Musicseerr/1.0 (https://github.com/HabiRabbu/Musicseerr)"


class HttpClientFactory:
    _clients: dict[str, httpx.AsyncClient] = {}
    
    @classmethod
    def get_client(
        cls,
        name: str = "default",
        timeout: float = 10.0,
        connect_timeout: float = 5.0,
        max_connections: int = 200,
        max_keepalive: int = 50,
        **kwargs
    ) -> httpx.AsyncClient:
        if name not in cls._clients:
            cls._clients[name] = httpx.AsyncClient(
                http2=True,
                timeout=httpx.Timeout(timeout, connect=connect_timeout),
                limits=httpx.Limits(
                    max_connections=max_connections,
                    max_keepalive_connections=max_keepalive,
                    keepalive_expiry=30.0,
                ),
                follow_redirects=True,
                transport=httpx.AsyncHTTPTransport(http2=True, retries=0),
                headers={"User-Agent": USER_AGENT},
                **kwargs
            )
        return cls._clients[name]
    
    @classmethod
    async def close_all(cls) -> None:
        for client in cls._clients.values():
            await client.aclose()
        cls._clients.clear()


def get_http_client(settings: Optional[Settings] = None) -> httpx.AsyncClient:
    if settings:
        return HttpClientFactory.get_client(
            name="default",
            timeout=settings.http_timeout,
            connect_timeout=settings.http_connect_timeout,
            max_connections=settings.http_max_connections,
            max_keepalive=settings.http_max_keepalive,
        )
    return HttpClientFactory.get_client()


async def close_http_clients() -> None:
    await HttpClientFactory.close_all()
