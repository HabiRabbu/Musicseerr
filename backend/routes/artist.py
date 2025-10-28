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
    
    has_annotation = "annotation" in mb_artist
    annotation_value = mb_artist.get("annotation")
    print(f"DEBUG - Artist: {mb_artist.get('name')}")
    print(f"  Has annotation key: {has_annotation}")
    if has_annotation:
        print(f"  Annotation type: {type(annotation_value)}")
        if isinstance(annotation_value, dict):
            print(f"  Annotation dict keys: {list(annotation_value.keys())}")
        elif isinstance(annotation_value, str):
            print(f"  Annotation length: {len(annotation_value)}")
    
    description = None
    if url_rels := mb_artist.get("url-relation-list", []):
        print(f"  URL relations count: {len(url_rels)}")
        wiki_urls = [
            url_rel.get("target") for url_rel in url_rels 
            if url_rel.get("type") in ("wikipedia", "wikidata")
        ]
        print(f"  Wikipedia/Wikidata URLs found: {len(wiki_urls)}")
        
        for url_rel in url_rels:
            url_type = url_rel.get("type")
            if url_type in ("wikipedia", "wikidata"):
                if wiki_url := url_rel.get("target"):
                    print(f"  Fetching from {url_type}: {wiki_url}")
                    description = await wikidata.get_wikipedia_extract(wiki_url)
                    if description:
                        print(f"  ✓ Got description (length: {len(description)})")
                        break
                    else:
                        print("  ✗ No description returned")
    else:
        print("  No URL relations found")
    
    if not description:
        print("  Final: No description available")
    
    albums, singles, eps = artist_parser.categorize_release_groups(mb_artist, album_mbids)
    
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
