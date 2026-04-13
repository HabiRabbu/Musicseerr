"""Tests for AudioDB settings, API key masking, round-trips, and validation."""

import pytest
import msgspec

from api.v1.schemas.advanced_settings import (
    AdvancedSettings,
    AdvancedSettingsFrontend,
    _mask_api_key,
    _is_masked_api_key,
)


class TestMaskApiKey:
    def test_long_key_shows_last_three(self) -> None:
        assert _mask_api_key("myapikey123") == "***...123"

    def test_four_char_key(self) -> None:
        assert _mask_api_key("1234") == "***...234"

    def test_three_char_key_fully_masked(self) -> None:
        assert _mask_api_key("123") == "***"

    def test_two_char_key_fully_masked(self) -> None:
        assert _mask_api_key("ab") == "***"

    def test_one_char_key_fully_masked(self) -> None:
        assert _mask_api_key("x") == "***"

    def test_empty_key_fully_masked(self) -> None:
        assert _mask_api_key("") == "***"


class TestIsMaskedApiKey:
    def test_masked_with_suffix(self) -> None:
        assert _is_masked_api_key("***...123") is True

    def test_masked_short(self) -> None:
        assert _is_masked_api_key("***") is True

    def test_plaintext_key(self) -> None:
        assert _is_masked_api_key("mynewkey") is False

    def test_empty_string(self) -> None:
        assert _is_masked_api_key("") is False

    def test_partial_asterisks(self) -> None:
        assert _is_masked_api_key("** not masked") is False

    def test_triple_asterisks_with_extra(self) -> None:
        assert _is_masked_api_key("***extra") is True


class TestApiKeyRoundTrip:
    def test_from_backend_masks_long_key(self) -> None:
        backend = AdvancedSettings(audiodb_api_key="secretkey")
        frontend = AdvancedSettingsFrontend.from_backend(backend)
        assert frontend.audiodb_api_key == "***...key"

    def test_from_backend_masks_default_key(self) -> None:
        backend = AdvancedSettings(audiodb_api_key="123")
        frontend = AdvancedSettingsFrontend.from_backend(backend)
        assert frontend.audiodb_api_key == "***"

    def test_to_backend_passes_masked_key_through(self) -> None:
        frontend = AdvancedSettingsFrontend(audiodb_api_key="***...key")
        backend = frontend.to_backend()
        assert backend.audiodb_api_key == "***...key"

    def test_to_backend_passes_new_plaintext_key(self) -> None:
        frontend = AdvancedSettingsFrontend(audiodb_api_key="newkey456")
        backend = frontend.to_backend()
        assert backend.audiodb_api_key == "newkey456"

    def test_default_api_key_is_123(self) -> None:
        settings = AdvancedSettings()
        assert settings.audiodb_api_key == "123"

    def test_frontend_default_api_key_is_123(self) -> None:
        frontend = AdvancedSettingsFrontend()
        assert frontend.audiodb_api_key == "123"


class TestApiKeyEmptyGuard:
    def test_empty_key_coerced_to_default(self) -> None:
        settings = AdvancedSettings(audiodb_api_key="")
        assert settings.audiodb_api_key == "123"

    def test_whitespace_key_coerced_to_default(self) -> None:
        settings = AdvancedSettings(audiodb_api_key="   ")
        assert settings.audiodb_api_key == "123"

    def test_valid_key_preserved(self) -> None:
        settings = AdvancedSettings(audiodb_api_key="premium_key")
        assert settings.audiodb_api_key == "premium_key"


class TestRecentlyViewedBytesTTLRoundTrip:
    def test_default_backend_value(self) -> None:
        settings = AdvancedSettings()
        assert settings.cache_ttl_recently_viewed_bytes == 172800

    def test_default_frontend_value(self) -> None:
        frontend = AdvancedSettingsFrontend()
        assert frontend.cache_ttl_recently_viewed_bytes == 48

    def test_roundtrip_preserves_value(self) -> None:
        backend = AdvancedSettings(cache_ttl_recently_viewed_bytes=172800)
        frontend = AdvancedSettingsFrontend.from_backend(backend)
        assert frontend.cache_ttl_recently_viewed_bytes == 48
        restored = frontend.to_backend()
        assert restored.cache_ttl_recently_viewed_bytes == 172800

    def test_roundtrip_custom_value(self) -> None:
        backend = AdvancedSettings(cache_ttl_recently_viewed_bytes=36000)
        frontend = AdvancedSettingsFrontend.from_backend(backend)
        assert frontend.cache_ttl_recently_viewed_bytes == 10
        restored = frontend.to_backend()
        assert restored.cache_ttl_recently_viewed_bytes == 36000

    def test_backend_validation_rejects_too_low(self) -> None:
        with pytest.raises(msgspec.ValidationError):
            AdvancedSettings(cache_ttl_recently_viewed_bytes=3599)

    def test_backend_validation_rejects_too_high(self) -> None:
        with pytest.raises(msgspec.ValidationError):
            AdvancedSettings(cache_ttl_recently_viewed_bytes=604801)

    def test_frontend_validation_rejects_too_high(self) -> None:
        with pytest.raises(msgspec.ValidationError):
            AdvancedSettingsFrontend(cache_ttl_recently_viewed_bytes=169)

    def test_frontend_validation_rejects_too_low(self) -> None:
        with pytest.raises(msgspec.ValidationError):
            AdvancedSettingsFrontend(cache_ttl_recently_viewed_bytes=0)
