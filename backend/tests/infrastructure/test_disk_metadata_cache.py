import hashlib
import json

import pytest

from api.v1.schemas.album import AlbumInfo
from infrastructure.cache.disk_cache import DiskMetadataCache


@pytest.mark.asyncio
async def test_set_album_serializes_msgspec_struct_as_mapping(tmp_path):
    cache = DiskMetadataCache(base_path=tmp_path)
    mbid = "4549a80c-efe6-4386-b3a2-4b4a918eb31f"
    album_info = AlbumInfo(
        title="The Moon Song",
        musicbrainz_id=mbid,
        artist_name="beabadoobee",
        artist_id="88d17133-abbc-42db-9526-4e2c1db60336",
        in_library=True,
    )

    await cache.set_album(mbid, album_info, is_monitored=True)

    cache_hash = hashlib.sha1(mbid.encode()).hexdigest()
    cache_file = tmp_path / "persistent" / "albums" / f"{cache_hash}.json"
    payload = json.loads(cache_file.read_text())

    assert isinstance(payload, dict)
    assert payload["musicbrainz_id"] == mbid

    cached = await cache.get_album(mbid)
    assert isinstance(cached, dict)
    assert cached["title"] == "The Moon Song"


@pytest.mark.asyncio
async def test_get_album_deletes_corrupt_string_payload(tmp_path):
    cache = DiskMetadataCache(base_path=tmp_path)
    mbid = "8e1e9e51-38dc-4df3-8027-a0ada37d4674"

    cache_hash = hashlib.sha1(mbid.encode()).hexdigest()
    cache_file = tmp_path / "persistent" / "albums" / f"{cache_hash}.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps("AlbumInfo(title='Corrupt')"))

    cached = await cache.get_album(mbid)

    assert cached is None
    assert not cache_file.exists()
