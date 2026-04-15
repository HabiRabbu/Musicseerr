from infrastructure.msgspec_fastapi import AppStruct


class VersionInfo(AppStruct):
    version: str
    build_date: str | None = None


class GitHubRelease(AppStruct):
    tag_name: str
    published_at: str
    html_url: str
    name: str | None = None
    body: str | None = None
    prerelease: bool = False


class UpdateCheckResponse(AppStruct):
    current_version: str
    latest_version: str | None = None
    update_available: bool = False
    comparison_failed: bool = False
    latest_release: GitHubRelease | None = None
