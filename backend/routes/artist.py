"""Artist detail endpoints."""
import asyncio
import logging

from fastapi import APIRouter, HTTPException

from models import ArtistInfo
from utils import musicbrainz, lidarr, wikidata, artist_parser
from utils.cache import cached

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/artist", tags=["artist"])


@router.get("/{artist_id}", response_model=ArtistInfo)
@cached(ttl_seconds=3600, key_prefix="artist:")
async def get_artist(artist_id: str):
    """Get detailed artist information."""
    try:
        # Parallel data fetching
        mb_artist, library_mbids, album_mbids = await asyncio.gather(
            musicbrainz.get_artist_by_id(artist_id),
            lidarr.get_artist_mbids(),
            lidarr.get_library_mbids(include_release_ids=True),
        )
    except Exception as e:
        logger.error(f"Error fetching artist data for {artist_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch artist: {e}")
    
    if not mb_artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    
    # Check if artist is in library
    in_library = artist_id.lower() in library_mbids
    
    # Parse artist data
    tags = artist_parser.extract_tags(mb_artist)
    aliases = artist_parser.extract_aliases(mb_artist)
    life_span = artist_parser.extract_life_span(mb_artist)
    external_links = artist_parser.extract_external_links(mb_artist)
    albums, singles, eps = artist_parser.categorize_release_groups(mb_artist, album_mbids)
    
    # Fetch Wikipedia description if available
    description = None
    if url_rels := mb_artist.get("url-relation-list", []):
        for url_rel in url_rels:
            url_type = url_rel.get("type")
            if url_type in ("wikipedia", "wikidata"):
                if wiki_url := url_rel.get("target"):
                    description = await wikidata.get_wikipedia_extract(wiki_url)
                    if description:
                        break
    
    return ArtistInfo(
        name=mb_artist.get("name", "Unknown Artist"),
        musicbrainz_id=artist_id,
        disambiguation=mb_artist.get("disambiguation"),
        type=mb_artist.get("type"),
        country=mb_artist.get("country"),
        life_span=life_span,
        description=description,
        tags=tags,
        aliases=aliases,
        external_links=external_links,
        in_library=in_library,
        albums=albums,
        singles=singles,
        eps=eps,
    )
