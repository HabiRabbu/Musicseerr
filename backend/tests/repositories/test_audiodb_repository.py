from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import msgspec
import pytest

from core.exceptions import ExternalServiceError, RateLimitedError
from repositories.audiodb_models import AudioDBAlbumResponse, AudioDBArtistResponse
from infrastructure.resilience.retry import CircuitBreaker
from repositories.audiodb_repository import (
    AUDIODB_FREE_KEY,
    AudioDBRepository,
    _audiodb_circuit_breaker,
    _make_rate_limiter,
)


def _make_advanced_settings(enabled: bool = True, api_key: str = "test_key") -> MagicMock:
    settings = MagicMock()
    settings.audiodb_enabled = enabled
    settings.audiodb_api_key = api_key
    return settings


def _make_repo(enabled: bool = True, api_key: str = "test_key", premium: bool = False) -> AudioDBRepository:
    client = AsyncMock(spec=httpx.AsyncClient)
    prefs = MagicMock()
    prefs.get_advanced_settings.return_value = _make_advanced_settings(enabled, api_key)
    return AudioDBRepository(
        http_client=client,
        preferences_service=prefs,
        api_key=api_key,
        premium=premium,
    )


def _mock_response(status_code: int = 200, json_data: dict | None = None) -> httpx.Response:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    if json_data is not None:
        resp.content = msgspec.json.encode(json_data)
    else:
        resp.content = b"{}"
    return resp


SAMPLE_ARTIST_DATA = {
    "idArtist": "111239",
    "strArtist": "Coldplay",
    "strMusicBrainzID": "cc197bad-dc9c-440d-a5b5-d52ba2e14234",
    "strArtistThumb": "https://r2.theaudiodb.com/images/artist/thumb/coldplay.jpg",
    "strArtistFanart": "https://r2.theaudiodb.com/images/artist/fanart/coldplay1.jpg",
    "strArtistFanart2": "https://r2.theaudiodb.com/images/artist/fanart/coldplay2.jpg",
    "strArtistFanart3": None,
    "strArtistFanart4": None,
    "strArtistWideThumb": "https://r2.theaudiodb.com/images/artist/widethumb/coldplay.jpg",
    "strArtistBanner": "https://r2.theaudiodb.com/images/artist/banner/coldplay.jpg",
    "strArtistLogo": None,
    "strArtistCutout": None,
    "strArtistClearart": None,
}

SAMPLE_ALBUM_DATA = {
    "idAlbum": "2115888",
    "strAlbum": "Parachutes",
    "strMusicBrainzID": "1dc4c347-a1db-32aa-b14f-bc9cc507b843",
    "strAlbumThumb": "https://r2.theaudiodb.com/images/album/thumb/parachutes.jpg",
    "strAlbumBack": "https://r2.theaudiodb.com/images/album/back/parachutes.jpg",
    "strAlbumCDart": None,
    "strAlbumSpine": None,
    "strAlbum3DCase": None,
    "strAlbum3DFlat": None,
    "strAlbum3DFace": None,
    "strAlbum3DThumb": None,
}

FULL_PAYLOAD_ARTIST_DATA = {
    **SAMPLE_ARTIST_DATA,
    "strArtistStripped": None,
    "strArtistAlternate": "",
    "strLabel": "Parlophone",
    "idLabel": "45114",
    "intFormedYear": "1996",
    "intBornYear": "1996",
    "intDiedYear": None,
    "strDisbanded": None,
    "strStyle": "Rock/Pop",
    "strGenre": "Alternative Rock",
    "strMood": "Happy",
    "strWebsite": "www.coldplay.com",
    "strFacebook": "",
    "strTwitter": "",
    "strBiographyEN": "Coldplay are a British rock band...",
    "strBiographyDE": None,
    "strBiographyFR": None,
    "strBiographyES": None,
    "strGender": "Male",
    "intMembers": "4",
    "strCountry": "London, England",
    "strCountryCode": "GB",
    "strArtistFanart5": None,
    "strArtistFanart6": None,
}

FULL_PAYLOAD_ALBUM_DATA = {
    **SAMPLE_ALBUM_DATA,
    "idArtist": "111239",
    "idLabel": "45114",
    "strArtist": "Coldplay",
    "strArtistStripped": None,
    "intYearReleased": "2000",
    "strStyle": "Rock/Pop",
    "strGenre": "Alternative Rock",
    "strLabel": "Parlophone",
    "strReleaseFormat": "Album",
    "intSales": "0",
    "strAlbumStripped": "Parachutes",
    "strDescriptionEN": "Parachutes is the debut studio album...",
    "strDescriptionDE": None,
    "strDescriptionFR": None,
    "strDescriptionES": None,
    "intScore": "8",
    "intScoreVotes": "5",
    "strReview": "",
    "strMood": "Happy",
    "strTheme": None,
    "strSpeed": None,
    "strLocation": None,
    "strMusicBrainzArtistID": "cc197bad-dc9c-440d-a5b5-d52ba2e14234",
    "strAllMusicID": None,
    "strBBCReviewID": None,
    "strRateYourMusicID": None,
    "strDiscogsID": None,
    "strWikidataID": None,
    "strWikipediaID": None,
    "strGeniusID": None,
    "strLyricWikiID": None,
    "strMusicMozID": None,
    "strItunesID": None,
    "strAmazonID": None,
    "strLocked": "unlocked",
}


@pytest.fixture(autouse=True)
def _reset_resilience():
    _audiodb_circuit_breaker.reset()
    yield
    _audiodb_circuit_breaker.reset()


@pytest.fixture(autouse=True)
def _stub_retry_sleep():
    with patch("infrastructure.resilience.retry.asyncio.sleep", new=AsyncMock()):
        yield



@pytest.mark.asyncio
async def test_get_artist_by_mbid_disabled():
    repo = _make_repo(enabled=False)
    result = await repo.get_artist_by_mbid("cc197bad-dc9c-440d-a5b5-d52ba2e14234")
    assert result is None
    repo._client.get.assert_not_called()


@pytest.mark.asyncio
async def test_get_album_by_mbid_disabled():
    repo = _make_repo(enabled=False)
    result = await repo.get_album_by_mbid("1dc4c347-a1db-32aa-b14f-bc9cc507b843")
    assert result is None
    repo._client.get.assert_not_called()


@pytest.mark.asyncio
async def test_search_artist_by_name_disabled():
    repo = _make_repo(enabled=False)
    result = await repo.search_artist_by_name("Coldplay")
    assert result is None
    repo._client.get.assert_not_called()


@pytest.mark.asyncio
async def test_search_album_by_name_disabled():
    repo = _make_repo(enabled=False)
    result = await repo.search_album_by_name("Coldplay", "Parachutes")
    assert result is None
    repo._client.get.assert_not_called()



@pytest.mark.asyncio
async def test_get_artist_by_mbid_empty():
    repo = _make_repo()
    result = await repo.get_artist_by_mbid("")
    assert result is None


@pytest.mark.asyncio
async def test_get_album_by_mbid_empty():
    repo = _make_repo()
    result = await repo.get_album_by_mbid("")
    assert result is None


@pytest.mark.asyncio
async def test_search_artist_by_name_empty():
    repo = _make_repo()
    result = await repo.search_artist_by_name("")
    assert result is None


@pytest.mark.asyncio
async def test_search_album_by_name_empty_artist():
    repo = _make_repo()
    result = await repo.search_album_by_name("", "Parachutes")
    assert result is None


@pytest.mark.asyncio
async def test_search_album_by_name_empty_album():
    repo = _make_repo()
    result = await repo.search_album_by_name("Coldplay", "")
    assert result is None



@pytest.mark.asyncio
async def test_get_artist_by_mbid_found():
    repo = _make_repo()
    response = _mock_response(200, {"artists": [SAMPLE_ARTIST_DATA]})
    repo._client.get = AsyncMock(return_value=response)

    result = await repo.get_artist_by_mbid("cc197bad-dc9c-440d-a5b5-d52ba2e14234")

    assert result is not None
    assert isinstance(result, AudioDBArtistResponse)
    assert result.strArtist == "Coldplay"
    assert result.strArtistThumb == "https://r2.theaudiodb.com/images/artist/thumb/coldplay.jpg"
    assert result.strMusicBrainzID == "cc197bad-dc9c-440d-a5b5-d52ba2e14234"


@pytest.mark.asyncio
async def test_get_album_by_mbid_found():
    repo = _make_repo()
    response = _mock_response(200, {"album": [SAMPLE_ALBUM_DATA]})
    repo._client.get = AsyncMock(return_value=response)

    result = await repo.get_album_by_mbid("1dc4c347-a1db-32aa-b14f-bc9cc507b843")

    assert result is not None
    assert isinstance(result, AudioDBAlbumResponse)
    assert result.strAlbum == "Parachutes"
    assert result.strAlbumThumb == "https://r2.theaudiodb.com/images/album/thumb/parachutes.jpg"


@pytest.mark.asyncio
async def test_search_artist_by_name_found():
    repo = _make_repo()
    response = _mock_response(200, {"artists": [SAMPLE_ARTIST_DATA]})
    repo._client.get = AsyncMock(return_value=response)

    result = await repo.search_artist_by_name("Coldplay")

    assert result is not None
    assert isinstance(result, AudioDBArtistResponse)
    assert result.strArtist == "Coldplay"


@pytest.mark.asyncio
async def test_search_album_by_name_found():
    repo = _make_repo()
    response = _mock_response(200, {"album": [SAMPLE_ALBUM_DATA]})
    repo._client.get = AsyncMock(return_value=response)

    result = await repo.search_album_by_name("Coldplay", "Parachutes")

    assert result is not None
    assert isinstance(result, AudioDBAlbumResponse)
    assert result.strAlbum == "Parachutes"


# These fixtures include many extra fields from real AudioDB responses
# to ensure unknown fields are silently ignored, not rejected.

@pytest.mark.asyncio
async def test_full_payload_artist_parses_successfully():
    repo = _make_repo()
    response = _mock_response(200, {"artists": [FULL_PAYLOAD_ARTIST_DATA]})
    repo._client.get = AsyncMock(return_value=response)

    result = await repo.get_artist_by_mbid("cc197bad-dc9c-440d-a5b5-d52ba2e14234")

    assert result is not None
    assert isinstance(result, AudioDBArtistResponse)
    assert result.strArtist == "Coldplay"
    assert result.idArtist == "111239"
    assert result.strArtistThumb == "https://r2.theaudiodb.com/images/artist/thumb/coldplay.jpg"
    assert result.strMusicBrainzID == "cc197bad-dc9c-440d-a5b5-d52ba2e14234"


@pytest.mark.asyncio
async def test_full_payload_album_parses_successfully():
    repo = _make_repo()
    response = _mock_response(200, {"album": [FULL_PAYLOAD_ALBUM_DATA]})
    repo._client.get = AsyncMock(return_value=response)

    result = await repo.get_album_by_mbid("1dc4c347-a1db-32aa-b14f-bc9cc507b843")

    assert result is not None
    assert isinstance(result, AudioDBAlbumResponse)
    assert result.strAlbum == "Parachutes"
    assert result.idAlbum == "2115888"
    assert result.strAlbumThumb == "https://r2.theaudiodb.com/images/album/thumb/parachutes.jpg"
    assert result.strMusicBrainzID == "1dc4c347-a1db-32aa-b14f-bc9cc507b843"



@pytest.mark.asyncio
async def test_get_artist_by_mbid_not_found_null():
    repo = _make_repo()
    response = _mock_response(200, {"artists": None})
    repo._client.get = AsyncMock(return_value=response)

    result = await repo.get_artist_by_mbid("00000000-0000-0000-0000-000000000000")
    assert result is None


@pytest.mark.asyncio
async def test_get_artist_by_mbid_not_found_empty():
    repo = _make_repo()
    response = _mock_response(200, {"artists": []})
    repo._client.get = AsyncMock(return_value=response)

    result = await repo.get_artist_by_mbid("00000000-0000-0000-0000-000000000000")
    assert result is None


@pytest.mark.asyncio
async def test_get_album_by_mbid_not_found():
    repo = _make_repo()
    response = _mock_response(200, {"album": None})
    repo._client.get = AsyncMock(return_value=response)

    result = await repo.get_album_by_mbid("00000000-0000-0000-0000-000000000000")
    assert result is None



@pytest.mark.asyncio
async def test_request_429(caplog):
    repo = _make_repo()
    response = _mock_response(429)
    repo._client.get = AsyncMock(return_value=response)

    with caplog.at_level("WARNING"), pytest.raises(RateLimitedError):
        await repo.get_artist_by_mbid("cc197bad-dc9c-440d-a5b5-d52ba2e14234")
    assert repo._client.get.call_count == 3
    assert _audiodb_circuit_breaker.failure_count == 1
    ratelimit_logs = [r.message for r in caplog.records if "audiodb.ratelimit" in r.message]
    assert len(ratelimit_logs) == 3
    assert all("retry_after_s=60" in msg for msg in ratelimit_logs)


@pytest.mark.asyncio
async def test_request_500():
    repo = _make_repo()
    response = _mock_response(500)
    repo._client.get = AsyncMock(return_value=response)

    with pytest.raises(ExternalServiceError):
        await repo.get_artist_by_mbid("cc197bad-dc9c-440d-a5b5-d52ba2e14234")


@pytest.mark.asyncio
async def test_request_404_returns_none():
    repo = _make_repo()
    response = _mock_response(404)
    repo._client.get = AsyncMock(return_value=response)

    result = await repo.get_artist_by_mbid("cc197bad-dc9c-440d-a5b5-d52ba2e14234")
    assert result is None


@pytest.mark.asyncio
async def test_request_timeout():
    repo = _make_repo()
    repo._client.get = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))

    with pytest.raises(ExternalServiceError):
        await repo.get_artist_by_mbid("cc197bad-dc9c-440d-a5b5-d52ba2e14234")


@pytest.mark.asyncio
async def test_request_connection_error():
    repo = _make_repo()
    repo._client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

    with pytest.raises(ExternalServiceError):
        await repo.get_artist_by_mbid("cc197bad-dc9c-440d-a5b5-d52ba2e14234")



@pytest.mark.asyncio
async def test_circuit_breaker_resets():
    _audiodb_circuit_breaker.record_failure()
    _audiodb_circuit_breaker.record_failure()
    _audiodb_circuit_breaker.record_failure()
    _audiodb_circuit_breaker.record_failure()
    _audiodb_circuit_breaker.record_failure()
    assert _audiodb_circuit_breaker.is_open()

    AudioDBRepository.reset_circuit_breaker()
    assert not _audiodb_circuit_breaker.is_open()



def test_rate_limiter_free_tier():
    limiter = _make_rate_limiter(premium=False)
    assert limiter.rate == 0.5
    assert limiter.capacity == 2


def test_rate_limiter_premium_tier():
    limiter = _make_rate_limiter(premium=True)
    assert limiter.rate == 5.0
    assert limiter.capacity == 10


def test_repo_uses_free_limiter():
    repo = _make_repo(api_key=AUDIODB_FREE_KEY, premium=False)
    assert repo._rate_limiter.rate == 0.5


def test_repo_uses_premium_limiter():
    repo = _make_repo(premium=True)
    assert repo._rate_limiter.rate == 5.0


def test_repo_custom_key_uses_free_limiter_by_default():
    repo = _make_repo(api_key="custom_key_abc")
    assert repo._rate_limiter.rate == 0.5



@pytest.mark.asyncio
async def test_url_contains_api_key_in_path():
    repo = _make_repo(api_key="my_test_key")
    response = _mock_response(200, {"artists": [SAMPLE_ARTIST_DATA]})
    repo._client.get = AsyncMock(return_value=response)

    await repo.get_artist_by_mbid("cc197bad-dc9c-440d-a5b5-d52ba2e14234")

    call_args = repo._client.get.call_args
    url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
    assert "my_test_key" in url
    assert "artist-mb.php" in url


@pytest.mark.asyncio
async def test_search_album_passes_both_params():
    repo = _make_repo()
    response = _mock_response(200, {"album": [SAMPLE_ALBUM_DATA]})
    repo._client.get = AsyncMock(return_value=response)

    await repo.search_album_by_name("Coldplay", "Parachutes")

    call_args = repo._client.get.call_args
    params = call_args[1].get("params", {}) if call_args[1] else {}
    assert params.get("s") == "Coldplay"
    assert params.get("a") == "Parachutes"



def test_half_open_requires_two_successes_to_close():
    breaker = CircuitBreaker(failure_threshold=5, success_threshold=2, timeout=0.0, name="test")
    for _ in range(5):
        breaker.record_failure()
    assert breaker.is_open() is False  # timeout=0 → auto-transitions to HALF_OPEN
    assert breaker.state.value == "half_open"

    breaker.record_success()
    assert breaker.state.value == "half_open"

    breaker.record_success()
    assert breaker.state.value == "closed"


def test_half_open_single_success_does_not_close():
    breaker = CircuitBreaker(failure_threshold=3, success_threshold=2, timeout=0.0, name="test2")
    for _ in range(3):
        breaker.record_failure()
    breaker.is_open()  # triggers HALF_OPEN transition
    assert breaker.state.value == "half_open"

    breaker.record_success()
    assert breaker.state.value == "half_open"

    breaker.record_failure()
    assert breaker.state.value == "open"



@pytest.mark.asyncio
async def test_get_artist_by_mbid_schema_error():
    repo = _make_repo()
    bad_data = {"artists": [{"unexpected_field": "value"}]}
    response = _mock_response(200, bad_data)
    repo._client.get = AsyncMock(return_value=response)

    result = await repo.get_artist_by_mbid("cc197bad-dc9c-440d-a5b5-d52ba2e14234")
    assert result is None


@pytest.mark.asyncio
async def test_get_album_by_mbid_schema_error():
    repo = _make_repo()
    bad_data = {"album": [{"unexpected_field": "value"}]}
    response = _mock_response(200, bad_data)
    repo._client.get = AsyncMock(return_value=response)

    result = await repo.get_album_by_mbid("1dc4c347-a1db-32aa-b14f-bc9cc507b843")
    assert result is None


@pytest.mark.asyncio
async def test_search_artist_schema_error():
    repo = _make_repo()
    bad_data = {"artists": [{"unexpected_field": "value"}]}
    response = _mock_response(200, bad_data)
    repo._client.get = AsyncMock(return_value=response)

    result = await repo.search_artist_by_name("Coldplay")
    assert result is None


@pytest.mark.asyncio
async def test_search_album_schema_error():
    repo = _make_repo()
    bad_data = {"album": [{"unexpected_field": "value"}]}
    response = _mock_response(200, bad_data)
    repo._client.get = AsyncMock(return_value=response)

    result = await repo.search_album_by_name("Coldplay", "Parachutes")
    assert result is None



@pytest.mark.asyncio
async def test_circuit_open_returns_none_for_artist_mbid():
    for _ in range(5):
        _audiodb_circuit_breaker.record_failure()
    assert _audiodb_circuit_breaker.is_open()

    repo = _make_repo()
    result = await repo.get_artist_by_mbid("cc197bad-dc9c-440d-a5b5-d52ba2e14234")
    assert result is None
    repo._client.get.assert_not_called()


@pytest.mark.asyncio
async def test_circuit_open_returns_none_for_album_mbid():
    for _ in range(5):
        _audiodb_circuit_breaker.record_failure()
    assert _audiodb_circuit_breaker.is_open()

    repo = _make_repo()
    result = await repo.get_album_by_mbid("1dc4c347-a1db-32aa-b14f-bc9cc507b843")
    assert result is None
    repo._client.get.assert_not_called()


@pytest.mark.asyncio
async def test_circuit_open_returns_none_for_artist_search():
    for _ in range(5):
        _audiodb_circuit_breaker.record_failure()
    assert _audiodb_circuit_breaker.is_open()

    repo = _make_repo()
    result = await repo.search_artist_by_name("Coldplay")
    assert result is None
    repo._client.get.assert_not_called()


@pytest.mark.asyncio
async def test_circuit_open_returns_none_for_album_search():
    for _ in range(5):
        _audiodb_circuit_breaker.record_failure()
    assert _audiodb_circuit_breaker.is_open()

    repo = _make_repo()
    result = await repo.search_album_by_name("Coldplay", "Parachutes")
    assert result is None
    repo._client.get.assert_not_called()



@pytest.mark.asyncio
async def test_retries_on_transient_error():
    repo = _make_repo()
    fail_resp = _mock_response(500)
    ok_resp = _mock_response(200, {"artists": [SAMPLE_ARTIST_DATA]})
    repo._client.get = AsyncMock(side_effect=[fail_resp, fail_resp, ok_resp])

    result = await repo.get_artist_by_mbid("cc197bad-dc9c-440d-a5b5-d52ba2e14234")
    assert result is not None
    assert result.strArtist == "Coldplay"
    assert repo._client.get.call_count == 3


@pytest.mark.asyncio
async def test_retries_exhausted_raises():
    repo = _make_repo()
    fail_resp = _mock_response(500)
    repo._client.get = AsyncMock(return_value=fail_resp)

    with pytest.raises(ExternalServiceError):
        await repo.get_artist_by_mbid("cc197bad-dc9c-440d-a5b5-d52ba2e14234")
    assert repo._client.get.call_count == 3


@pytest.mark.asyncio
async def test_rate_limit_failures_open_circuit_and_short_circuit_next_lookup():
    repo = _make_repo()
    response = _mock_response(429)
    repo._client.get = AsyncMock(return_value=response)

    for _ in range(5):
        with pytest.raises(RateLimitedError):
            await repo.get_artist_by_mbid("cc197bad-dc9c-440d-a5b5-d52ba2e14234")

    assert _audiodb_circuit_breaker.is_open()
    call_count_before = repo._client.get.call_count

    result = await repo.get_artist_by_mbid("cc197bad-dc9c-440d-a5b5-d52ba2e14234")

    assert result is None
    assert repo._client.get.call_count == call_count_before


@pytest.mark.asyncio
async def test_audiodb_specific_circuit_state_change_logs(caplog):
    repo = _make_repo()
    fail_resp = _mock_response(500)
    success_resp = _mock_response(200, {"artists": [SAMPLE_ARTIST_DATA]})
    repo._client.get = AsyncMock(return_value=fail_resp)

    with caplog.at_level("INFO"):
        for _ in range(5):
            with pytest.raises(ExternalServiceError):
                await repo.get_artist_by_mbid("cc197bad-dc9c-440d-a5b5-d52ba2e14234")

        _audiodb_circuit_breaker.last_failure_time -= _audiodb_circuit_breaker.timeout + 1
        repo._client.get = AsyncMock(return_value=success_resp)

        first_result = await repo.get_artist_by_mbid("cc197bad-dc9c-440d-a5b5-d52ba2e14234")
        second_result = await repo.get_artist_by_mbid("cc197bad-dc9c-440d-a5b5-d52ba2e14234")

    assert first_result is not None
    assert second_result is not None

    state_change_logs = [record.message for record in caplog.records if record.message.startswith("audiodb.circuit_state_change")]
    assert any("state=open" in message for message in state_change_logs)
    assert any("state=half_open" in message for message in state_change_logs)
    assert any("state=closed" in message for message in state_change_logs)




class TestEffectiveApiKey:
    def test_prefers_settings_key_over_constructor(self):
        repo = _make_repo(api_key="constructor_key")
        repo._preferences_service.get_advanced_settings.return_value = (
            _make_advanced_settings(api_key="settings_key")
        )
        assert repo._effective_api_key() == "settings_key"

    def test_falls_back_to_constructor_when_settings_empty(self):
        repo = _make_repo(api_key="constructor_key")
        repo._preferences_service.get_advanced_settings.return_value = (
            _make_advanced_settings(api_key="")
        )
        assert repo._effective_api_key() == "constructor_key"

    def test_falls_back_to_constructor_when_settings_whitespace(self):
        repo = _make_repo(api_key="constructor_key")
        repo._preferences_service.get_advanced_settings.return_value = (
            _make_advanced_settings(api_key="   ")
        )
        assert repo._effective_api_key() == "constructor_key"

    @pytest.mark.asyncio
    async def test_request_uses_settings_key_not_constructor(self):
        repo = _make_repo(api_key="constructor_key")
        repo._preferences_service.get_advanced_settings.return_value = (
            _make_advanced_settings(api_key="settings_key")
        )
        response = _mock_response(200, {"artists": [SAMPLE_ARTIST_DATA]})
        repo._client.get = AsyncMock(return_value=response)

        await repo.get_artist_by_mbid("cc197bad-dc9c-440d-a5b5-d52ba2e14234")

        url = repo._client.get.call_args[0][0]
        assert "settings_key" in url
        assert "constructor_key" not in url
