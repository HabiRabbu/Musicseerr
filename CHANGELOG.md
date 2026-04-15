# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Added

- **Plex SSO login** — users can sign in with their Plex account instead of a local password. The backend exchanges the OAuth token for user info via plex.tv, verifies the user has access to the configured Plex server, and auto-creates a local account on first sign-in.
- **Emby SSO login** — users can sign in with their Emby username and password. Credentials are validated directly against the configured Emby server (`/Users/AuthenticateByName`). Configure the server URL under Settings > Users & Access > Authentication Providers. Includes a Test Connection button.
- **Per-user request limits** — admins can set a global request quota (max requests per N days) that applies to all regular users. Per-user overrides are also supported. Admins are always unlimited. Users who exceed their quota receive a clear `429` error. New `requested_by` column in request history tracks who made each request.
- **User management UI** — Settings > Users & Access now shows a full user table (admin-only) with inline editing for role, request permissions, and quota overrides. Users can be promoted, demoted, or removed.
- **Admin API** — new `/api/v1/admin/users` and `/api/v1/admin/settings/requests` endpoints for managing users and default quota settings programmatically.
- **`emby_enabled` in auth status** — `/api/v1/auth/status` now includes `emby_enabled` so the login page can show the Emby sign-in option only when it is configured.

### Fixed

- **Library sync status showing "Failed" while sync is running** — the Last Sync stat now shows "In progress" while `syncStatus.isActive` is true, preventing the stale `last_sync_success: false` from a previous run being displayed during an active sync.

---

## [Post-1.0 — Authentication & Security]

_Committed changes after the initial public release, prior to the unreleased work above._

### Added

- **Optional user authentication** (`e1f5e95`) — full opt-in login system with local accounts (username + password), JWT session tokens, and admin/user roles. Auth can be toggled on/off without losing accounts. First account is created at `/setup`.
- **Security headers** (`efce77b`) — `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Referrer-Policy`, and `Permissions-Policy` headers on every response.
- **Credential masking** (`36ad938`) — all API keys, tokens, and secrets are masked in settings API responses so they are never exposed to the browser after being saved.
- **Avatar file validation** (`faff2a2`) — avatar uploads validate magic bytes against the declared `Content-Type` to prevent content-type spoofing.
- **Rate limiting tightened** (`efce77b`) — stricter per-path rate limits on credential-sensitive endpoints (verify, OAuth flows). Interactive API docs disabled in production.
- **Purple/blue logo variant** (`6158606`) — updated icon with purple-filled eye interior.

### Fixed

- **Auth token not injected in raw fetch calls** (`403f352`) — all direct `fetch()` calls in the frontend now attach the Bearer token.
- **/setup link not clickable when enabling auth with no users** (`9bbaf1c`, `f06e258`) — replaced the inline text link with a proper button and ensured it is always reachable.

### Changed

- **CI: single-pass multi-arch builds** (`83de121`) — Docker images are now built once per architecture and merged into a manifest list, halving CI time.

---

## [1.0.0] — Initial Public Release

_`a99c738` — first public release. All features below were present at launch._

### Added

- Search the full MusicBrainz catalogue for artists and albums.
- Request albums via Lidarr with a persistent request queue, status tracking, retry, and cancel.
- Built-in audio player with Jellyfin, Navidrome, Plex, local files, and YouTube sources.
- 10-band equalizer with presets, shuffle, seek, and volume control.
- Home page with trending artists, popular albums, recently added, genre quick-links, ListenBrainz weekly playlists, and personalised "Because You Listened To" carousels.
- Discover page with a recommendation queue drawn from similar artists, library gaps, fresh releases, and listening history.
- Browse by genre, trending/popular charts, and personal top albums.
- Library views for Lidarr, Jellyfin, Navidrome, Plex, local files.
- Scrobbling to ListenBrainz and Last.fm simultaneously.
- Playlists with cross-source tracks, drag-to-reorder, and custom cover art.
- Profile page with display name, avatar, connected services, and library stats.
- Robust library sync with adaptive watchdog and resume-on-failure.
- Lidarr integration: album request, library sync, artist monitoring.
- Jellyfin integration: streaming, library, MBID index, playback reporting.
- Navidrome integration: Subsonic API streaming and library browsing.
- Plex integration: direct-play streaming, multi-library, native scrobbling, OAuth token flow.
- ListenBrainz integration: scrobbling, discovery, weekly playlists, top charts.
- Last.fm integration: scrobbling, OAuth session.
- YouTube integration: auto-link and manual-link album playback.
- Local files integration: direct-serve from mounted music directory.
- TheAudioDB integration: high-quality artist/album artwork with cache TTL controls.
- Cover Art Archive and Wikidata for metadata enrichment.
- Single Docker container deployment (PUID/PGID, timezone, health check).
- Unraid/NAS support with UMASK config and permissive entrypoint hardening.
