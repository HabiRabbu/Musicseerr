from fastapi import APIRouter, HTTPException
from models import ArtistInfo
from utils import musicbrainz, lidarr, wikidata, artist_parser

router = APIRouter(prefix="/api/artist", tags=["artist"])


@router.get("/{artist_id}", response_model=ArtistInfo)
async def get_artist(artist_id: str):
    mb_artist = await musicbrainz.get_artist_by_id(artist_id)
    
    if not mb_artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    
    library_mbids = await lidarr.get_artist_mbids()
    in_library = artist_id.lower() in library_mbids
    
    album_mbids = await lidarr.get_library_mbids(include_release_ids=True)
    
    tags = artist_parser.extract_tags(mb_artist)
    aliases = artist_parser.extract_aliases(mb_artist)
    life_span = artist_parser.extract_life_span(mb_artist)
    external_links = artist_parser.extract_external_links(mb_artist)
    
    wikipedia_description = None
    if url_rels := mb_artist.get("url-relation-list", []):
        for url_rel in url_rels:
            if url_rel.get("type") == "wikipedia":
                if wikipedia_url := url_rel.get("target"):
                    wikipedia_description = await wikidata.get_wikipedia_extract(wikipedia_url)
                    if wikipedia_description:
                        break
    
    description = wikipedia_description or mb_artist.get("annotation")
    
    albums, singles, eps = artist_parser.categorize_release_groups(mb_artist, album_mbids)
    
    return ArtistInfo(
        name=mb_artist.get("name", "Unknown Artist"),
        musicbrainz_id=artist_id,
        disambiguation=mb_artist.get("disambiguation"),
        type=mb_artist.get("type"),
        country=mb_artist.get("country"),
        life_span=life_span,
        annotation=description,
        tags=tags,
        aliases=aliases,
        external_links=external_links,
        in_library=in_library,
        albums=albums,
        singles=singles,
        eps=eps,
    )
