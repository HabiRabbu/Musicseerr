import re
from typing import Optional
from urllib.parse import quote

from http_client import client
from utils.cache import get_cache

_cache = get_cache()


async def get_wikidata_id_from_url(wikidata_url: str) -> Optional[str]:
    match = re.search(r'/wiki/(Q\d+)', wikidata_url)
    return match.group(1) if match else None


async def get_artist_image_from_wikidata(wikidata_id: str) -> Optional[str]:
    cache_key = f"wikidata_image:{wikidata_id}"
    
    cached = await _cache.get(cache_key)
    if cached is not None:
        return cached
    
    try:
        wikidata_url = f"https://www.wikidata.org/wiki/Special:EntityData/{wikidata_id}.json"
        response = await client.get(wikidata_url)
        
        if response.status_code != 200:
            await _cache.set(cache_key, None, ttl_seconds=300)
            return None
        
        data = response.json()
        entity = data.get("entities", {}).get(wikidata_id, {})
        
        image_claims = entity.get("claims", {}).get("P18", [])
        if not image_claims:
            await _cache.set(cache_key, None, ttl_seconds=3600)
            return None
        
        image_filename = image_claims[0]["mainsnak"]["datavalue"]["value"]
        
        commons_url = (
            f"https://commons.wikimedia.org/w/api.php"
            f"?action=query&titles=File:{quote(image_filename)}"
            f"&prop=imageinfo&iiprop=url&format=json"
        )
        
        response = await client.get(commons_url)
        if response.status_code != 200:
            await _cache.set(cache_key, None, ttl_seconds=300)
            return None
        
        commons_data = response.json()
        pages = commons_data.get("query", {}).get("pages", {})
        
        for page_data in pages.values():
            imageinfo = page_data.get("imageinfo", [])
            if imageinfo and isinstance(imageinfo, list):
                image_url = imageinfo[0].get("url")
                if image_url:
                    await _cache.set(cache_key, image_url, ttl_seconds=3600)
                    return image_url
        
        await _cache.set(cache_key, None, ttl_seconds=3600)
        return None
            
    except Exception:
        await _cache.set(cache_key, None, ttl_seconds=300)
        return None

