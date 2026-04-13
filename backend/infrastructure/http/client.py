import httpx
from typing import Optional
from core.config import Settings, get_settings


def _get_user_agent(settings: Optional[Settings] = None) -> str:
    if settings:
        return settings.get_user_agent()
    return get_settings().get_user_agent()


class HttpClientFactory:
    _clients: dict[str, httpx.AsyncClient] = {}
    
    @classmethod
    def get_client(
        cls,
        name: str = "default",
        timeout: float = 10.0,
        connect_timeout: float = 5.0,
        max_connections: int = 200,
        max_keepalive: int = 200,
        settings: Optional[Settings] = None,
        http2: bool = True,
        **kwargs
    ) -> httpx.AsyncClient:
        if name not in cls._clients:
            cls._clients[name] = httpx.AsyncClient(
                http2=http2,
                timeout=httpx.Timeout(timeout, connect=connect_timeout),
                limits=httpx.Limits(
                    max_connections=max_connections,
                    max_keepalive_connections=max_keepalive,
                    keepalive_expiry=60.0,
                ),
                follow_redirects=True,
                transport=httpx.AsyncHTTPTransport(http2=http2, retries=0),
                headers={"User-Agent": _get_user_agent(settings)},
                **kwargs
            )
        return cls._clients[name]
    
    @classmethod
    async def close_all(cls) -> None:
        for client in cls._clients.values():
            await client.aclose()
        cls._clients.clear()


def get_http_client(
    settings: Optional[Settings] = None,
    timeout: Optional[float] = None,
    connect_timeout: Optional[float] = None,
    max_connections: Optional[int] = None,
) -> httpx.AsyncClient:
    if settings is None:
        settings = get_settings()
    return HttpClientFactory.get_client(
        name="default",
        timeout=timeout or settings.http_timeout,
        connect_timeout=connect_timeout or settings.http_connect_timeout,
        max_connections=max_connections or settings.http_max_connections,
        max_keepalive=settings.http_max_keepalive,
        settings=settings,
    )


async def close_http_clients() -> None:
    await HttpClientFactory.close_all()


def get_listenbrainz_http_client(
    settings: Optional[Settings] = None,
    timeout: Optional[float] = None,
    connect_timeout: Optional[float] = None,
) -> httpx.AsyncClient:
    if settings is None:
        settings = get_settings()
    return HttpClientFactory.get_client(
        name="listenbrainz",
        timeout=timeout or settings.http_timeout,
        connect_timeout=connect_timeout or settings.http_connect_timeout,
        max_connections=20,
        max_keepalive=20,
        settings=settings,
        http2=False,
    )
