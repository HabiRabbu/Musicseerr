import asyncio
from asyncio import log
from fastapi import APIRouter, Query
from utils import musicbrainz, lidarr

router = APIRouter(prefix="/api/search")


@router.get("", response_model=dict)
async def search(
    q: str = Query(..., min_length=1),
    type: str | None = Query(
        None, pattern="^(album|artist)$", description="Limit search results to this type."
    ),
):

    mb_task = asyncio.create_task(musicbrainz.search_musicbrainz(q, type=type))
    lib_task = asyncio.create_task(lidarr.get_library_mbids(include_release_ids=True))

    mb_results = []
    library_mbids: set[str] = set()

    try:
        mb_results, library_mbids = await asyncio.gather(mb_task, lib_task)
    except Exception as e:
        if mb_task.done() and mb_task.exception():
            raise mb_task.exception()
        log.warning(f"Lidarr unavailable during search: {e}")
        mb_results = mb_results or await mb_task

    for result in mb_results:
        if (
            result.type in {"album", "release", "release-group"}
            and result.musicbrainz_id
            and result.musicbrainz_id.lower() in library_mbids
        ):
            result.in_library = True
        else:
            result.in_library = False

    return {"results": mb_results}
