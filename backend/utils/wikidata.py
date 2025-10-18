import re
from typing import Optional
from urllib.parse import quote

from http_client import client
from utils.cache import get_cache

_cache = get_cache()


async def get_wikipedia_extract(wikipedia_url: str, lang: str = "en") -> Optional[str]:
    cache_key = f"wikipedia_extract:{wikipedia_url}"
    
    cached = await _cache.get(cache_key)
    if cached is not None:
        return cached
    
    try:
        wikidata_match = re.search(r'wikidata\.org/wiki/(Q\d+)', wikipedia_url)
        if wikidata_match:
            wikidata_id = wikidata_match.group(1)
            
            wikidata_api_url = f"https://www.wikidata.org/wiki/Special:EntityData/{wikidata_id}.json"
            response = await client.get(wikidata_api_url)
            
            if response.status_code != 200:
                await _cache.set(cache_key, None, ttl_seconds=3600)
                return None
            
            data = response.json()
            entity = data.get("entities", {}).get(wikidata_id, {})
            
            sitelinks = entity.get("sitelinks", {})
            en_wiki = sitelinks.get("enwiki", {})
            
            if not en_wiki:
                await _cache.set(cache_key, None, ttl_seconds=3600)
                return None
            
            page_title = en_wiki.get("title")
            if not page_title:
                await _cache.set(cache_key, None, ttl_seconds=3600)
                return None
        else:
            match = re.search(r'/wiki/(.+)$', wikipedia_url)
            if not match:
                await _cache.set(cache_key, None, ttl_seconds=3600)
                return None
            
            page_title = match.group(1)
        
        api_url = (
            f"https://{lang}.wikipedia.org/w/api.php"
            f"?action=query&titles={quote(page_title)}"
            f"&prop=extracts&exintro=1&explaintext=1&format=json"
        )
        
        response = await client.get(api_url)
        
        if response.status_code != 200:
            await _cache.set(cache_key, None, ttl_seconds=300)
            return None
        
        data = response.json()
        pages = data.get("query", {}).get("pages", {})
        
        for page_data in pages.values():
            if page_data.get("pageid", -1) < 0:
                await _cache.set(cache_key, None, ttl_seconds=3600)
                return None
            
            extract = page_data.get("extract")
            if extract:
                await _cache.set(cache_key, extract, ttl_seconds=604800)
                return extract
        
        await _cache.set(cache_key, None, ttl_seconds=3600)
        return None
            
    except Exception as e:
        print(f"ERROR: Exception fetching Wikipedia extract for {wikipedia_url}: {e}")
        await _cache.set(cache_key, None, ttl_seconds=300)
        return None


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

