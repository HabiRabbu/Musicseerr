from infrastructure.msgspec_fastapi import AppStruct


class AuthStatusResponse(AppStruct):
    auth_enabled: bool
    setup_required: bool


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
