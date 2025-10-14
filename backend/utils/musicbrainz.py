import asyncio
from typing import Any

import musicbrainzngs

from models import SearchResult

musicbrainzngs.set_useragent("Musicseerr", "1.0", "https://github.com/HabiRabbu/musicseerr")


async def search_musicbrainz(
    q: str, limit: int = 10, type: str | None = None
) -> list[SearchResult]:

    def sync_search() -> dict[str, Any]:
        results: dict[str, Any] = {}
        if type is None or type == "artist":
            results["artist-list"] = musicbrainzngs.search_artists(query=q, limit=limit).get(
                "artist-list", []
            )
        if type is None or type == "album":
            results["release-group-list"] = musicbrainzngs.search_release_groups(
                query=q, limit=limit
            ).get("release-group-list", [])
        return results

    results = await asyncio.to_thread(sync_search)
    final: list[SearchResult] = []

    for artist in results.get("artist-list", []):
        final.append(
            SearchResult(
                type="artist",
                title=artist.get("name"),
                artist=None,
                year=None,
                musicbrainz_id=artist.get("id"),
                in_library=False,
            )
        )

    for rg in results.get("release-group-list", []):
        artist_credit = rg.get("artist-credit", [{}])
        artist_name = artist_credit[0].get("name") if artist_credit else None
        year = None
        if date := rg.get("first-release-date"):
            try:
                year = int(date.split("-")[0])
            except ValueError:
                pass

        final.append(
            SearchResult(
                type="album",
                title=rg.get("title"),
                artist=artist_name,
                year=year,
                musicbrainz_id=rg.get("id"),
                in_library=False,
            )
        )

    return final
