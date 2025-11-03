"""Shared HTTP client for making external API calls."""
import httpx

client = httpx.AsyncClient(
    http2=True,
    timeout=httpx.Timeout(10.0, connect=5.0),
    limits=httpx.Limits(
        max_connections=200,
        max_keepalive_connections=50,
        keepalive_expiry=30.0,
    ),
    follow_redirects=True,
    transport=httpx.AsyncHTTPTransport(http2=True, retries=2),
)


async def aclose() -> None:
    """Close the HTTP client gracefully."""
    await client.aclose()
