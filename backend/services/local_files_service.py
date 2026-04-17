import asyncio
import logging
import os
import re
import shutil
import tempfile
import zipfile
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import aiofiles

from api.v1.schemas.local_files import (
    FormatInfo,
    LocalAlbumMatch,
    LocalAlbumSummary,
    LocalPaginatedResponse,
    LocalStorageStats,
    LocalTrackInfo,
)
from api.v1.schemas.settings import LocalFilesVerifyResponse
from core.exceptions import ExternalServiceError, ResourceNotFoundError
from infrastructure.cache.cache_keys import LOCAL_FILES_PREFIX
from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.cover_urls import prefer_release_group_cover_url
from infrastructure.constants import STREAM_CHUNK_SIZE
from infrastructure.resilience.retry import CircuitOpenError
from infrastructure.serialization import to_jsonable
from repositories.protocols import LidarrRepositoryProtocol
from services.preferences_service import PreferencesService

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS: set[str] = {
    ".flac", ".mp3", ".ogg", ".m4a", ".aac", ".wav", ".wma", ".opus",
}

CONTENT_TYPE_MAP: dict[str, str] = {
    ".flac": "audio/flac",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".wav": "audio/wav",
    ".wma": "audio/x-ms-wma",
    ".opus": "audio/opus",
}

_INVALID_FILENAME_CHARS = re.compile(r'[\x00-\x1f\\/:*?"<>|]')


def sanitize_filename(name: str) -> str:
    """Replace characters that are invalid in filenames across OS platforms."""
    return _INVALID_FILENAME_CHARS.sub("_", name).strip() or "Untitled"


class LocalFilesService:
    _DEFAULT_STORAGE_STATS_TTL = 300
    _ALBUM_LIST_TTL = 120
    _DEFAULT_RECENTLY_ADDED_TTL = 120

    def __init__(
        self,
        lidarr_repo: LidarrRepositoryProtocol,
        preferences_service: PreferencesService,
        cache: CacheInterface,
    ):
        self._lidarr = lidarr_repo
        self._preferences = preferences_service
        self._cache = cache

    def _get_config(self) -> tuple[str, str]:
        settings = self._preferences.get_local_files_connection()
        return settings.music_path, settings.lidarr_root_path

    def _get_recently_added_ttl(self) -> int:
        try:
            return self._preferences.get_advanced_settings().cache_ttl_local_files_recently_added
        except Exception:  # noqa: BLE001
            return self._DEFAULT_RECENTLY_ADDED_TTL

    def _get_storage_stats_ttl(self) -> int:
        try:
            return self._preferences.get_advanced_settings().cache_ttl_local_files_storage_stats
        except Exception:  # noqa: BLE001
            return self._DEFAULT_STORAGE_STATS_TTL

    def _remap_path(self, lidarr_path: str) -> Path:
        music_path, lidarr_root = self._get_config()
        lidarr_root = lidarr_root.rstrip("/")
        lidarr_root_parts = Path(lidarr_root).parts
        lidarr_path_obj = Path(lidarr_path)
        lidarr_path_parts = lidarr_path_obj.parts

        if (
            len(lidarr_path_parts) >= len(lidarr_root_parts)
            and lidarr_path_parts[: len(lidarr_root_parts)] == lidarr_root_parts
        ):
            relative = Path(*lidarr_path_parts[len(lidarr_root_parts):])
        else:
            relative = Path(lidarr_path.lstrip("/"))
        return Path(music_path) / relative

    async def _fetch_all_albums(self) -> list[dict[str, Any]]:
        cache_key = "local_files_all_albums"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            data = await self._lidarr.get_all_albums()
        except (ExternalServiceError, CircuitOpenError, ConnectionError, OSError):
            # Serve the last cached data if Lidarr is unavailable.
            try:
                stale = await self._cache.get(f"{cache_key}:stale")
            except Exception:  # noqa: BLE001
                stale = None
            if stale is not None:
                return stale
            raise
        result = data or []
        if result:
            await self._cache.set(cache_key, result, ttl_seconds=self._ALBUM_LIST_TTL)
            # Keep a longer-lived fallback copy for 24 hours.
            await self._cache.set(f"{cache_key}:stale", result, ttl_seconds=86400)
        return result

    def _resolve_and_validate_path(self, lidarr_path: str) -> Path:
        music_path, _ = self._get_config()
        resolved = self._remap_path(lidarr_path)
        canonical = resolved.resolve()
        music_root = Path(music_path).resolve()

        if not canonical.is_relative_to(music_root):
            raise PermissionError("Path outside music directory")
        if not canonical.exists():
            raise ResourceNotFoundError(f"File not found: {canonical.name}")
        return canonical

    async def get_track_file_path(self, track_file_id: int) -> str:
        try:
            data = await self._lidarr.get_track_file(track_file_id)
            if not data:
                raise ResourceNotFoundError(f"Track file {track_file_id} not found in Lidarr")
            path = data.get("path", "")
            return path
        except ResourceNotFoundError:
            raise
        except Exception as e:  # noqa: BLE001
            raise ExternalServiceError(f"Failed to get track file from Lidarr: {e}")

    async def head_track(self, track_file_id: int) -> dict[str, str]:
        lidarr_path = await self.get_track_file_path(track_file_id)
        file_path = self._resolve_and_validate_path(lidarr_path)

        suffix = file_path.suffix.lower()
        if suffix not in AUDIO_EXTENSIONS:
            raise ExternalServiceError(
                f"Unsupported audio format: {suffix or 'unknown'}"
            )

        try:
            stat_result = await asyncio.to_thread(file_path.stat)
        except OSError as exc:
            raise ResourceNotFoundError(
                f"Cannot access file: {file_path.name} ({exc})"
            )

        content_type = CONTENT_TYPE_MAP.get(suffix, "application/octet-stream")
        return {
            "Content-Type": content_type,
            "Content-Length": str(stat_result.st_size),
            "Accept-Ranges": "bytes",
        }

    async def stream_track(
        self,
        track_file_id: int,
        range_header: str | None = None,
    ) -> tuple[AsyncGenerator[bytes, None], dict[str, str], int]:
        lidarr_path = await self.get_track_file_path(track_file_id)
        file_path = self._resolve_and_validate_path(lidarr_path)

        suffix = file_path.suffix.lower()
        if suffix not in AUDIO_EXTENSIONS:
            raise ExternalServiceError(
                f"Unsupported audio format: {suffix or 'unknown'}"
            )

        try:
            stat_result = await asyncio.to_thread(file_path.stat)
        except OSError as exc:
            raise ResourceNotFoundError(
                f"Cannot access file: {file_path.name} ({exc})"
            )

        file_size = stat_result.st_size
        content_type = CONTENT_TYPE_MAP.get(suffix, "application/octet-stream")

        if range_header and range_header.startswith("bytes="):
            range_spec = range_header[6:]
            start_str, _, end_str = range_spec.partition("-")

            try:
                if not start_str and end_str:
                    suffix_len = int(end_str)
                    start = max(0, file_size - suffix_len)
                    end = file_size - 1
                elif start_str and not end_str:
                    start = int(start_str)
                    end = file_size - 1
                elif start_str and end_str:
                    start = int(start_str)
                    end = int(end_str)
                else:
                    raise ValueError("Empty range")
            except ValueError:
                return self._iter_file(file_path, 0, file_size), {
                    "Content-Type": content_type,
                    "Content-Length": str(file_size),
                    "Accept-Ranges": "bytes",
                }, 200

            end = min(end, file_size - 1)
            if start < 0 or start > end or start >= file_size:
                raise ExternalServiceError(
                    f"Range not satisfiable: {range_header} (file size: {file_size})"
                )

            length = end - start + 1

            headers = {
                "Content-Type": content_type,
                "Content-Length": str(length),
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
            }
            return self._iter_file(file_path, start, length), headers, 206

        headers = {
            "Content-Type": content_type,
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
        }
        return self._iter_file(file_path, 0, file_size), headers, 200

    async def _iter_file(
        self, path: Path, offset: int, length: int
    ) -> AsyncGenerator[bytes, None]:
        remaining = length
        try:
            async with aiofiles.open(path, "rb") as f:
                await f.seek(offset)
                while remaining > 0:
                    chunk_size = min(STREAM_CHUNK_SIZE, remaining)
                    data = await f.read(chunk_size)
                    if not data:
                        break
                    remaining -= len(data)
                    yield data
        except OSError as exc:
            logger.warning(
                "Local file read error mid-stream",
                extra={"path": str(path), "error": str(exc)},
            )

    async def get_album_track_files(
        self, lidarr_album_id: int
    ) -> list[dict[str, Any]]:
        data = await self._lidarr.get_track_files_by_album(lidarr_album_id)
        if not data:
            return []

        track_files = []
        for tf in data:
            path_str: str = tf.get("path", "")
            suffix = Path(path_str).suffix.lower().lstrip(".")
            quality = tf.get("quality", {})
            quality_detail = quality.get("quality", {})

            track_files.append({
                "track_file_id": tf.get("id"),
                "path": path_str,
                "size_bytes": tf.get("size", 0),
                "format": suffix if suffix else "unknown",
                "bitrate": quality_detail.get("bitrate"),
                "date_added": tf.get("dateAdded"),
            })

        return track_files

    async def _build_track_list(
        self, album_id: int
    ) -> tuple[list[LocalTrackInfo], int, dict[str, int]]:
        tracks = await self._lidarr.get_album_tracks(album_id)
        track_files = await self.get_album_track_files(album_id)

        file_map: dict[int, dict[str, Any]] = {
            tf["track_file_id"]: tf for tf in track_files if tf.get("track_file_id")
        }

        result: list[LocalTrackInfo] = []
        total_size = 0
        format_counts: dict[str, int] = {}

        for track in tracks:
            tf_id = track.get("track_file_id")
            has_file = track.get("has_file", False)
            if not has_file or not tf_id:
                continue

            tf = file_map.get(tf_id, {})
            fmt = tf.get("format", "unknown")
            size = tf.get("size_bytes", 0)
            total_size += size
            format_counts[fmt] = format_counts.get(fmt, 0) + 1

            raw_track_num = track.get("track_number") or track.get("position") or 0
            raw_disc_num = track.get("disc_number", 1) or 1
            try:
                track_num = int(raw_track_num)
            except (TypeError, ValueError):
                track_num = 0
            try:
                disc_num = int(raw_disc_num)
            except (TypeError, ValueError):
                disc_num = 1

            result.append(LocalTrackInfo(
                track_file_id=tf_id,
                title=track.get("title", "Unknown"),
                track_number=track_num,
                disc_number=disc_num,
                duration_seconds=(track.get("duration_ms", 0) or 0) / 1000.0,
                size_bytes=size,
                format=fmt,
                bitrate=tf.get("bitrate"),
                date_added=tf.get("date_added"),
            ))

        return result, total_size, format_counts

    async def match_album_by_mbid(
        self, musicbrainz_id: str
    ) -> LocalAlbumMatch:
        album_data = await self._lidarr.get_album_details(musicbrainz_id)
        if not album_data:
            return LocalAlbumMatch(found=False)

        album_id: int = album_data.get("id", 0)
        if not album_id:
            return LocalAlbumMatch(found=False)

        result_tracks, total_size, format_counts = await self._build_track_list(album_id)
        primary_format = max(format_counts, key=lambda k: format_counts[k]) if format_counts else None

        return LocalAlbumMatch(
            found=bool(result_tracks),
            lidarr_album_id=album_id,
            tracks=result_tracks,
            total_size_bytes=total_size,
            primary_format=primary_format,
        )

    async def get_download_track(self, track_file_id: int) -> tuple[Path, str, str]:
        """Resolve a track file for download. Returns (path, filename, media_type)."""
        lidarr_path = await self.get_track_file_path(track_file_id)
        file_path = self._resolve_and_validate_path(lidarr_path)
        suffix = file_path.suffix.lower()
        if suffix not in AUDIO_EXTENSIONS:
            raise ExternalServiceError(f"Unsupported audio format: {suffix}")
        media_type = CONTENT_TYPE_MAP.get(suffix, "application/octet-stream")
        filename = file_path.name
        return file_path, filename, media_type

    async def create_album_zip(self, album_id: int) -> tuple[Path, str]:
        """Build a ZIP of all tracks in an album. Returns (zip_path, zip_filename)."""
        album_data = await self._lidarr.get_album_by_id(album_id)
        if not album_data:
            raise ResourceNotFoundError(f"Album {album_id} not found in Lidarr")

        album_title = album_data.get("title") or "Unknown Album"
        artist_data = album_data.get("artist") or {}
        artist_name = artist_data.get("artistName") or "Unknown Artist"

        result_tracks, _, _ = await self._build_track_list(album_id)
        if not result_tracks:
            raise ResourceNotFoundError(f"No track files found for album {album_id}")

        # Pre-resolve all paths in the async context
        resolved: list[tuple[Path, LocalTrackInfo]] = []
        for track in result_tracks:
            try:
                lidarr_path = await self.get_track_file_path(track.track_file_id)
                file_path = self._resolve_and_validate_path(lidarr_path)
                resolved.append((file_path, track))
            except (ResourceNotFoundError, PermissionError, ExternalServiceError):
                logger.warning(
                    "Skipping track %s in album %s ZIP",
                    track.track_file_id,
                    album_id,
                )
                continue

        if not resolved:
            raise ResourceNotFoundError(f"No accessible files for album {album_id}")

        zip_filename = sanitize_filename(f"{artist_name} - {album_title}.zip")
        tmp_path = await asyncio.to_thread(self._write_zip_sync, resolved)
        return tmp_path, zip_filename

    async def create_album_zip_by_mbid(self, mbid: str) -> tuple[Path, str]:
        """Build a ZIP by MusicBrainz release-group ID."""
        album_data = await self._lidarr.get_album_by_mbid(mbid)
        if not album_data:
            raise ResourceNotFoundError(f"Album with MBID {mbid} not found in Lidarr")
        album_id = album_data.get("id")
        if not album_id:
            raise ResourceNotFoundError(f"Album with MBID {mbid} has no Lidarr ID")
        return await self.create_album_zip(album_id)

    @staticmethod
    def _write_zip_sync(
        resolved: list[tuple[Path, "LocalTrackInfo"]],
    ) -> Path:
        tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        try:
            multi_disc = len({t.disc_number for _, t in resolved}) > 1
            with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED) as zf:
                for file_path, track in sorted(
                    resolved, key=lambda r: (r[1].disc_number, r[1].track_number)
                ):
                    ext = file_path.suffix.lower()
                    title = sanitize_filename(track.title)
                    if multi_disc:
                        arcname = f"{track.disc_number:02d}-{track.track_number:02d} {title}{ext}"
                    else:
                        arcname = f"{track.track_number:02d} {title}{ext}"
                    zf.write(file_path, arcname)
            tmp.close()
            return Path(tmp.name)
        except BaseException:
            tmp.close()
            Path(tmp.name).unlink(missing_ok=True)
            raise

    def _library_album_to_summary(
        self, item: Any, album_id: int, track_file_count: int
    ) -> LocalAlbumSummary:
        artist_data = item.get("artist", {})
        year = None
        if date := item.get("releaseDate"):
            try:
                year = int(date.split("-")[0])
            except ValueError:
                pass

        mbid = item.get("foreignAlbumId", "")
        cover_url = None
        images = item.get("images", [])
        for img in images:
            if img.get("coverType") == "cover":
                cover_url = img.get("remoteUrl") or img.get("url")
                break
        if not cover_url and images:
            cover_url = images[0].get("remoteUrl") or images[0].get("url")
        cover_url = prefer_release_group_cover_url(mbid, cover_url, size=500)

        total_size = item.get("statistics", {}).get("sizeOnDisk", 0)

        return LocalAlbumSummary(
            lidarr_album_id=album_id,
            musicbrainz_id=mbid,
            name=item.get("title", "Unknown"),
            artist_name=artist_data.get("artistName", "Unknown"),
            artist_mbid=artist_data.get("foreignArtistId"),
            year=year,
            track_count=track_file_count,
            total_size_bytes=total_size,
            cover_url=cover_url,
            date_added=item.get("added"),
        )

    async def get_albums(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "name",
        sort_order: str = "asc",
        search_query: str | None = None,
    ) -> LocalPaginatedResponse:
        all_albums = await self._fetch_all_albums()

        albums_with_files: list[dict[str, Any]] = []
        for item in all_albums:
            stats = item.get("statistics", {})
            track_file_count = stats.get("trackFileCount", 0)
            if track_file_count > 0:
                albums_with_files.append(item)

        if search_query:
            q = search_query.lower()
            albums_with_files = [
                a for a in albums_with_files
                if q in a.get("title", "").lower()
                or q in a.get("artist", {}).get("artistName", "").lower()
            ]

        descending = sort_order == "desc"
        if sort_by == "date_added":
            albums_with_files.sort(
                key=lambda a: a.get("added", "") or "",
                reverse=descending,
            )
        elif sort_by == "year":
            albums_with_files.sort(
                key=lambda a: a.get("releaseDate", "") or "",
                reverse=descending,
            )
        else:
            albums_with_files.sort(
                key=lambda a: a.get("title", "").lower(),
                reverse=descending,
            )

        total = len(albums_with_files)
        page_items = albums_with_files[offset : offset + limit]

        summaries = [
            self._library_album_to_summary(
                item,
                item.get("id", 0),
                item.get("statistics", {}).get("trackFileCount", 0),
            )
            for item in page_items
        ]

        return LocalPaginatedResponse(
            items=summaries, total=total, offset=offset, limit=limit
        )

    async def get_album_tracks_by_id(
        self, lidarr_album_id: int
    ) -> list[LocalTrackInfo]:
        result, _, _ = await self._build_track_list(lidarr_album_id)
        return result

    async def search(self, query: str) -> list[LocalAlbumSummary]:
        result = await self.get_albums(
            limit=50, offset=0, search_query=query
        )
        return result.items

    async def get_recently_added(
        self, limit: int = 20
    ) -> list[LocalAlbumSummary]:
        ttl_seconds = self._get_recently_added_ttl()
        cache_key = f"{LOCAL_FILES_PREFIX}recently_added:{limit}"
        cached = await self._cache.get(cache_key)
        if isinstance(cached, list):
            try:
                return [
                    LocalAlbumSummary(**item)
                    for item in cached
                    if isinstance(item, dict)
                ]
            except (TypeError, ValueError):
                logger.debug("Ignoring invalid cached recently-added payload")

        recently_imported = await self._lidarr.get_recently_imported(limit=limit)
        if not recently_imported:
            await self._cache.set(
                cache_key, [], ttl_seconds=ttl_seconds
            )
            return []

        all_albums = await self._fetch_all_albums()
        album_lookup: dict[str, dict[str, Any]] = {}
        for album in all_albums:
            mbid = album.get("foreignAlbumId")
            if mbid:
                album_lookup[mbid] = album

        summaries: list[LocalAlbumSummary] = []
        for lib_album in recently_imported:
            mbid = lib_album.musicbrainz_id
            full = album_lookup.get(mbid) if mbid else None
            if full:
                stats = full.get("statistics", {})
                if stats.get("trackFileCount", 0) == 0:
                    continue
                summaries.append(
                    self._library_album_to_summary(
                        full,
                        full.get("id", 0),
                        stats.get("trackFileCount", 0),
                    )
                )
            else:
                summaries.append(
                    LocalAlbumSummary(
                        lidarr_album_id=0,
                        musicbrainz_id=mbid or "",
                        name=lib_album.album or "Unknown",
                        artist_name=lib_album.artist,
                        artist_mbid=lib_album.artist_mbid,
                        year=lib_album.year,
                        cover_url=lib_album.cover_url,
                        date_added=str(lib_album.date_added) if lib_album.date_added else None,
                    )
                )

        await self._cache.set(
            cache_key,
            [to_jsonable(summary) for summary in summaries],
            ttl_seconds=ttl_seconds,
        )
        return summaries

    async def get_storage_stats(self) -> LocalStorageStats:
        ttl_seconds = self._get_storage_stats_ttl()
        cache_key = "local_files_storage_stats"
        cached = await self._cache.get(cache_key)
        if cached and isinstance(cached, dict):
            try:
                return LocalStorageStats(**cached)
            except (TypeError, ValueError):
                logger.debug("Ignoring invalid cached local storage stats payload")

        music_path, _ = self._get_config()
        root = Path(music_path)
        if not root.exists():
            return LocalStorageStats()
        stats = await asyncio.to_thread(self._scan_storage_sync, root)

        await self._cache.set(
            cache_key, to_jsonable(stats), ttl_seconds=ttl_seconds
        )
        return stats

    def _scan_storage_sync(self, root: Path) -> LocalStorageStats:
        total_tracks = 0
        total_size = 0
        format_breakdown: dict[str, dict[str, int]] = {}
        album_dirs: set[str] = set()
        artist_dirs: set[str] = set()

        try:
            for dirpath, _dirs, files in os.walk(root):
                rel = Path(dirpath).relative_to(root)
                parts = rel.parts
                if len(parts) >= 1:
                    artist_dirs.add(parts[0])
                if len(parts) >= 2:
                    album_dirs.add(f"{parts[0]}/{parts[1]}")

                for fname in files:
                    ext = Path(fname).suffix.lower()
                    if ext not in AUDIO_EXTENSIONS:
                        continue
                    total_tracks += 1
                    fp = Path(dirpath) / fname
                    try:
                        sz = fp.stat().st_size
                    except OSError:
                        sz = 0
                    total_size += sz

                    fmt = ext.lstrip(".")
                    if fmt not in format_breakdown:
                        format_breakdown[fmt] = {"count": 0, "size_bytes": 0}
                    format_breakdown[fmt]["count"] += 1
                    format_breakdown[fmt]["size_bytes"] += sz

        except PermissionError:
            logger.warning("Permission denied scanning music directory")

        disk = shutil.disk_usage(root)

        typed_breakdown: dict[str, FormatInfo] = {}
        for fmt_name, fmt_data in format_breakdown.items():
            typed_breakdown[fmt_name] = FormatInfo(
                count=fmt_data["count"],
                size_bytes=fmt_data["size_bytes"],
                size_human=self._human_size(fmt_data["size_bytes"]),
            )

        return LocalStorageStats(
            total_tracks=total_tracks,
            total_albums=len(album_dirs),
            total_artists=len(artist_dirs),
            total_size_bytes=total_size,
            total_size_human=self._human_size(total_size),
            disk_free_bytes=disk.free,
            disk_free_human=self._human_size(disk.free),
            format_breakdown=typed_breakdown,
        )

    @staticmethod
    def _human_size(size_bytes: int) -> str:
        size = float(size_bytes)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if abs(size) < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"

    async def verify_path(self, music_path_str: str) -> LocalFilesVerifyResponse:
        return await asyncio.to_thread(self._verify_path_sync, music_path_str)

    def _verify_path_sync(self, music_path_str: str) -> LocalFilesVerifyResponse:
        music_path = Path(music_path_str)
        if not music_path.exists():
            return LocalFilesVerifyResponse(success=False, message=f"Path does not exist: {music_path_str}")
        if not music_path.is_dir():
            return LocalFilesVerifyResponse(success=False, message=f"Path is not a directory: {music_path_str}")
        if not os.access(music_path, os.R_OK):
            return LocalFilesVerifyResponse(success=False, message=f"Path is not readable: {music_path_str}")

        track_count = 0
        try:
            for _root, _dirs, files in os.walk(music_path):
                track_count += sum(1 for f in files if Path(f).suffix.lower() in AUDIO_EXTENSIONS)
                if track_count > 50000:
                    break
        except PermissionError:
            return LocalFilesVerifyResponse(success=False, message="Permission denied while scanning directory")

        return LocalFilesVerifyResponse(
            success=True,
            message=f"Connected, found {track_count:,} audio files",
            track_count=track_count,
        )
