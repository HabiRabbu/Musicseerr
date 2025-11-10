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
