import re
from typing import Optional
from urllib.parse import quote

from http_client import client
from utils.cache import cached

@cached(ttl_seconds=604800, key_prefix="wiki_extract:")
async def get_wikipedia_extract(wikipedia_url: str, lang: str = "en") -> Optional[str]:
    try:
        wikidata_match = re.search(r'wikidata\.org/wiki/(Q\d+)', wikipedia_url)
        if wikidata_match:
            wikidata_id = wikidata_match.group(1)
            
            wikidata_api_url = f"https://www.wikidata.org/wiki/Special:EntityData/{wikidata_id}.json"
            response = await client.get(wikidata_api_url)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            entity = data.get("entities", {}).get(wikidata_id, {})
            
            sitelinks = entity.get("sitelinks", {})
            en_wiki = sitelinks.get("enwiki", {})
            
            if not en_wiki:
                return None
            
            page_title = en_wiki.get("title")
            if not page_title:
                return None
        else:
            match = re.search(r'/wiki/(.+)$', wikipedia_url)
            if not match:
                return None
            
            page_title = match.group(1)
        
        api_url = (
            f"https://{lang}.wikipedia.org/w/api.php"
            f"?action=query&titles={quote(page_title)}"
            f"&prop=extracts&exintro=1&explaintext=1&format=json"
        )
        
        response = await client.get(api_url)
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        pages = data.get("query", {}).get("pages", {})
        
        for page_data in pages.values():
            if page_data.get("pageid", -1) < 0:
                return None
            
            extract = page_data.get("extract")
            if extract:
                return extract
        
        return None
            
    except Exception:
        return None


async def get_wikidata_id_from_url(wikidata_url: str) -> Optional[str]:
    match = re.search(r'/wiki/(Q\d+)', wikidata_url)
    return match.group(1) if match else None


@cached(ttl_seconds=86400, key_prefix="wikidata_img:")
async def get_artist_image_from_wikidata(wikidata_id: str) -> Optional[str]:
    try:
        wikidata_url = f"https://www.wikidata.org/wiki/Special:EntityData/{wikidata_id}.json"
        response = await client.get(wikidata_url)
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        entity = data.get("entities", {}).get(wikidata_id, {})
        
        image_claims = entity.get("claims", {}).get("P18", [])
        if not image_claims:
            return None
        
        image_filename = image_claims[0]["mainsnak"]["datavalue"]["value"]
        
        commons_url = (
            f"https://commons.wikimedia.org/w/api.php"
            f"?action=query&titles=File:{quote(image_filename)}"
            f"&prop=imageinfo&iiprop=url&format=json"
        )
        
        response = await client.get(commons_url)
        if response.status_code != 200:
            return None
        
        commons_data = response.json()
        pages = commons_data.get("query", {}).get("pages", {})
        
        for page_data in pages.values():
            imageinfo = page_data.get("imageinfo", [])
            if imageinfo and isinstance(imageinfo, list):
                image_url = imageinfo[0].get("url")
                if image_url:
                    return image_url
        
        return None
            
    except Exception:
        return None

