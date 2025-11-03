"""Wikidata and Wikipedia API integration."""
import logging
import re
from typing import Optional
from urllib.parse import quote

from http_client import client
from utils.cache import cached

logger = logging.getLogger(__name__)


def _extract_wikidata_id(url: str) -> Optional[str]:
    """Extract Wikidata ID from URL."""
    match = re.search(r'/wiki/(Q\d+)', url)
    return match.group(1) if match else None


def _extract_wikipedia_title(url: str) -> Optional[str]:
    """Extract Wikipedia page title from URL."""
    match = re.search(r'/wiki/(.+)$', url)
    return match.group(1) if match else None


async def _get_wikipedia_title_from_wikidata(wikidata_id: str, lang: str = "en") -> Optional[str]:
    """Get Wikipedia page title from Wikidata ID."""
    try:
        api_url = f"https://www.wikidata.org/wiki/Special:EntityData/{wikidata_id}.json"
        response = await client.get(api_url)
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        entity = data.get("entities", {}).get(wikidata_id, {})
        sitelinks = entity.get("sitelinks", {})
        wiki_data = sitelinks.get(f"{lang}wiki", {})
        
        return wiki_data.get("title")
    
    except Exception as e:
        logger.error(f"Failed to get Wikipedia title for {wikidata_id}: {e}")
        return None


async def _fetch_wikipedia_extract(page_title: str, lang: str = "en") -> Optional[str]:
    """Fetch Wikipedia extract for a page title."""
    try:
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
            
            if extract := page_data.get("extract"):
                return extract
        
        return None
    
    except Exception as e:
        logger.error(f"Failed to fetch Wikipedia extract: {e}")
        return None


@cached(ttl_seconds=604800, key_prefix="wiki_extract:")
async def get_wikipedia_extract(wikipedia_url: str, lang: str = "en") -> Optional[str]:
    """Get Wikipedia article extract from URL.
    
    Args:
        wikipedia_url: Wikipedia or Wikidata URL
        lang: Language code (default: "en")
    
    Returns:
        Article extract text or None
    """
    try:
        # Handle Wikidata URLs
        if wikidata_id := _extract_wikidata_id(wikipedia_url):
            page_title = await _get_wikipedia_title_from_wikidata(wikidata_id, lang)
            if not page_title:
                return None
        
        # Handle Wikipedia URLs
        elif page_title := _extract_wikipedia_title(wikipedia_url):
            pass
        
        else:
            return None
        
        return await _fetch_wikipedia_extract(page_title, lang)
    
    except Exception as e:
        logger.error(f"Failed to get Wikipedia extract from {wikipedia_url}: {e}")
        return None


async def get_wikidata_id_from_url(wikidata_url: str) -> Optional[str]:
    """Extract Wikidata ID from URL."""
    return _extract_wikidata_id(wikidata_url)


@cached(ttl_seconds=86400, key_prefix="wikidata_img:")
async def get_artist_image_from_wikidata(wikidata_id: str) -> Optional[str]:
    """Get artist image URL from Wikidata.
    
    Args:
        wikidata_id: Wikidata entity ID (e.g., "Q1234")
    
    Returns:
        Image URL or None
    """
    try:
        # Get Wikidata entity
        entity_url = f"https://www.wikidata.org/wiki/Special:EntityData/{wikidata_id}.json"
        response = await client.get(entity_url)
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        entity = data.get("entities", {}).get(wikidata_id, {})
        
        # Get image filename from P18 (image) claim
        image_claims = entity.get("claims", {}).get("P18", [])
        if not image_claims:
            return None
        
        image_filename = image_claims[0]["mainsnak"]["datavalue"]["value"]
        
        # Get image URL from Wikimedia Commons
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
            if imageinfo := page_data.get("imageinfo"):
                if isinstance(imageinfo, list) and imageinfo:
                    return imageinfo[0].get("url")
        
        return None
    
    except Exception as e:
        logger.error(f"Failed to get image for Wikidata {wikidata_id}: {e}")
        return None