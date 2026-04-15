from infrastructure.msgspec_fastapi import AppStruct


class AuthStatusResponse(AppStruct):
    auth_enabled: bool
    setup_required: bool
    emby_enabled: bool = False


class AuthLoginRequest(AppStruct):
    username: str
    password: str


class AuthLoginResponse(AppStruct):
    token: str
    username: str
    role: str


class AuthSetupRequest(AppStruct):
    username: str
    password: str


class AuthSettingsResponse(AppStruct):
    enabled: bool


class PlexLoginRequest(AppStruct):
    plex_token: str


class EmbyLoginRequest(AppStruct):
    username: str
    password: str


class UserSummary(AppStruct):
    username: str
    role: str
    auth_provider: str | None = None
    can_request: bool = True
    request_quota: int | None = None
    quota_days: int | None = None


class UpdateUserRequest(AppStruct):
    role: str | None = None
    can_request: bool | None = None
    request_quota: int | None = None
    quota_days: int | None = None
    clear_quota: bool = False


class DefaultRequestSettings(AppStruct):
    quota: int | None = None
    quota_days: int = 7
    can_request: bool = True
