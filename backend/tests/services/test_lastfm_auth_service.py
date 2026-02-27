import time

import pytest
from unittest.mock import AsyncMock, MagicMock

from core.exceptions import ConfigurationError
from repositories.lastfm_models import LastFmSession, LastFmToken
from services.lastfm_auth_service import (
    LastFmAuthService,
    MAX_PENDING_TOKENS,
    TOKEN_TTL_SECONDS,
)


def _make_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_token = AsyncMock(return_value=LastFmToken(token="test-token-abc"))
    repo.get_session = AsyncMock(
        return_value=LastFmSession(name="testuser", key="sk-123", subscriber=0)
    )
    return repo


@pytest.fixture
def service():
    repo = _make_repo()
    svc = LastFmAuthService(lastfm_repo=repo)
    return svc, repo


@pytest.mark.asyncio
async def test_request_token_returns_token_and_auth_url(service):
    svc, repo = service
    token, auth_url = await svc.request_token("my-api-key")
    assert token == "test-token-abc"
    assert "my-api-key" in auth_url
    assert "test-token-abc" in auth_url
    repo.get_token.assert_called_once()


@pytest.mark.asyncio
async def test_request_token_stores_in_pending(service):
    svc, _repo = service
    token, _ = await svc.request_token("key")
    assert token in svc._pending_tokens


@pytest.mark.asyncio
async def test_exchange_session_returns_username_and_key(service):
    svc, _repo = service
    token, _ = await svc.request_token("key")
    username, session_key, _ = await svc.exchange_session(token)
    assert username == "testuser"
    assert session_key == "sk-123"


@pytest.mark.asyncio
async def test_exchange_session_removes_from_pending(service):
    svc, _repo = service
    token, _ = await svc.request_token("key")
    await svc.exchange_session(token)
    assert token not in svc._pending_tokens


@pytest.mark.asyncio
async def test_exchange_session_rejects_unknown_token(service):
    svc, _repo = service
    with pytest.raises(ConfigurationError, match="expired or not recognized"):
        await svc.exchange_session("never-requested-token")


@pytest.mark.asyncio
async def test_expired_tokens_are_evicted(service):
    svc, _repo = service
    token, _ = await svc.request_token("key")
    svc._pending_tokens[token].created_at = time.time() - TOKEN_TTL_SECONDS - 1

    with pytest.raises(ConfigurationError, match="expired or not recognized"):
        await svc.exchange_session(token)


@pytest.mark.asyncio
async def test_max_pending_tokens_evicts_oldest(service):
    svc, repo = service
    tokens = []
    for i in range(MAX_PENDING_TOKENS):
        repo.get_token.return_value = LastFmToken(token=f"tok-{i}")
        tok, _ = await svc.request_token("key")
        tokens.append(tok)

    assert len(svc._pending_tokens) == MAX_PENDING_TOKENS

    repo.get_token.return_value = LastFmToken(token="tok-new")
    await svc.request_token("key")
    assert len(svc._pending_tokens) == MAX_PENDING_TOKENS
    assert tokens[0] not in svc._pending_tokens
    assert "tok-new" in svc._pending_tokens
