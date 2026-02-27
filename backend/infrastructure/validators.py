import re
from typing import Optional

MBID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)


def is_valid_mbid(mbid: Optional[str]) -> bool:
    if not mbid or not isinstance(mbid, str):
        return False
    
    mbid = mbid.strip()
    
    if mbid.startswith('unknown_'):
        return False
    
    return bool(MBID_PATTERN.match(mbid))


def validate_mbid(mbid: Optional[str], entity_type: str = "entity") -> str:
    if not mbid or not isinstance(mbid, str):
        raise ValueError(f"Invalid {entity_type} MBID: must be a non-empty string")
    
    mbid = mbid.strip()
    
    if not mbid:
        raise ValueError(f"Invalid {entity_type} MBID: empty string")
    
    if mbid.startswith('unknown_'):
        raise ValueError(f"Cannot process unknown {entity_type} MBID: {mbid}")
    
    if not MBID_PATTERN.match(mbid):
        raise ValueError(f"Invalid {entity_type} MBID format: {mbid}")
    
    return mbid


def is_unknown_mbid(mbid: Optional[str]) -> bool:
    return not mbid or not isinstance(mbid, str) or mbid.startswith('unknown_') or not mbid.strip()


def sanitize_optional_string(value: Optional[str]) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    
    value = value.strip()
    return value if value else None


def strip_html_tags(text: str | None) -> str:
    """Strip HTML tags from text, converting <br> to newlines.

    Uses stdlib html.parser — no external dependencies needed.
    Returns plain text suitable for display.
    """
    if not text:
        return ""

    from html.parser import HTMLParser
    from html import unescape

    class _TextExtractor(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self._parts: list[str] = []

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag in ("br", "br/"):
                self._parts.append("\n")

        def handle_endtag(self, tag: str) -> None:
            if tag == "p":
                self._parts.append("\n\n")

        def handle_data(self, data: str) -> None:
            self._parts.append(data)

        def get_text(self) -> str:
            return "".join(self._parts).strip()

    extractor = _TextExtractor()
    extractor.feed(unescape(text))
    return extractor.get_text()


_LASTFM_SUFFIX_RE = re.compile(
    r"\s*Read more on Last\.fm\.?\s*$",
    re.IGNORECASE,
)


def clean_lastfm_bio(text: str | None) -> str:
    """Strip HTML tags and remove the trailing 'Read more on Last.fm' suffix."""
    cleaned = strip_html_tags(text)
    if not cleaned:
        return ""
    return _LASTFM_SUFFIX_RE.sub("", cleaned).rstrip()
