import httpx
import logging
import re
from typing import Optional
from urllib.parse import quote
from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.cache.cache_keys import (
    wikipedia_extract_key,
    wikidata_artist_image_key,
)
from infrastructure.resilience.retry import with_retry, CircuitBreaker

logger = logging.getLogger(__name__)

_wikidata_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    success_threshold=2,
    timeout=60.0,
    name="wikidata"
)


class WikidataRepository:
    def __init__(self, http_client: httpx.AsyncClient, cache: CacheInterface):
        self._client = http_client
        self._cache = cache
    
    @staticmethod
    def _extract_wikidata_id(url: str) -> Optional[str]:
        match = re.search(r'/wiki/(Q\d+)', url)
        return match.group(1) if match else None
    
    @staticmethod
    def _extract_wikipedia_title(url: str) -> Optional[str]:
        match = re.search(r'/wiki/(.+)$', url)
        return match.group(1) if match else None
    
    @with_retry(
        max_attempts=3,
        base_delay=0.5,
        max_delay=3.0,
        circuit_breaker=_wikidata_circuit_breaker,
        retriable_exceptions=(httpx.HTTPError,)
    )
    async def _get_wikipedia_title_from_wikidata(
        self,
        wikidata_id: str,
        lang: str = "en"
    ) -> Optional[str]:
        try:
            api_url = f"https://www.wikidata.org/wiki/Special:EntityData/{wikidata_id}.json"
            response = await self._client.get(api_url)
            
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
    
    @with_retry(
        max_attempts=3,
        base_delay=0.5,
        max_delay=3.0,
        circuit_breaker=_wikidata_circuit_breaker,
        retriable_exceptions=(httpx.HTTPError,)
    )
    async def _fetch_wikipedia_extract(self, page_title: str, lang: str = "en") -> Optional[str]:
        try:
            api_url = (
                f"https://{lang}.wikipedia.org/w/api.php"
                f"?action=query&titles={quote(page_title)}"
                f"&prop=extracts&exintro=1&explaintext=1&format=json"
            )
            
            response = await self._client.get(api_url)
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
    
    async def get_wikipedia_extract(self, wikipedia_url: str, lang: str = "en") -> Optional[str]:
        cache_key = wikipedia_extract_key(wikipedia_url)
        
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            if wikidata_id := self._extract_wikidata_id(wikipedia_url):
                page_title = await self._get_wikipedia_title_from_wikidata(wikidata_id, lang)
                if not page_title:
                    return None
            
            elif page_title := self._extract_wikipedia_title(wikipedia_url):
                pass
            
            else:
                return None
            
            extract = await self._fetch_wikipedia_extract(page_title, lang)
            
            if extract:
                await self._cache.set(cache_key, extract, ttl_seconds=604800)
            
            return extract
        
        except Exception as e:
            logger.error(f"Failed to get Wikipedia extract from {wikipedia_url}: {e}")
            return None
    
    def get_wikidata_id_from_url(self, wikidata_url: str) -> Optional[str]:
        return self._extract_wikidata_id(wikidata_url)
    
    async def get_artist_image_from_wikidata(self, wikidata_id: str) -> Optional[str]:
        cache_key = wikidata_artist_image_key(wikidata_id)
        
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            entity_url = f"https://www.wikidata.org/wiki/Special:EntityData/{wikidata_id}.json"
            response = await self._client.get(entity_url)
            
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
            
            response = await self._client.get(commons_url)
            if response.status_code != 200:
                return None
            
            commons_data = response.json()
            pages = commons_data.get("query", {}).get("pages", {})
            
            for page_data in pages.values():
                if imageinfo := page_data.get("imageinfo"):
                    if isinstance(imageinfo, list) and imageinfo:
                        image_url = imageinfo[0].get("url")
                        if image_url:
                            await self._cache.set(cache_key, image_url, ttl_seconds=86400)
                        return image_url
            
            return None
        
        except Exception as e:
            logger.error(f"Failed to get image for Wikidata {wikidata_id}: {e}")
            return None
