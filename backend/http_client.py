import httpx

client = httpx.AsyncClient(
    http2=True,
    timeout=10.0,
    limits=httpx.Limits(
        max_connections=100,
        max_keepalive_connections=20
    ),
    follow_redirects=True
)


async def aclose():
    """Close the shared HTTP client on shutdown."""
    await client.aclose()
