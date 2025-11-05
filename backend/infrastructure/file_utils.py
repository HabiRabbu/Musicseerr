"""File operation utilities with atomic writes and thread safety."""
import json
import logging
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Global lock for file operations to ensure thread safety
_file_locks: dict[str, threading.Lock] = {}
_locks_lock = threading.Lock()


def _get_file_lock(file_path: Path) -> threading.Lock:
    """Get or create a lock for a specific file path."""
    path_str = str(file_path.resolve())
    with _locks_lock:
        if path_str not in _file_locks:
            _file_locks[path_str] = threading.Lock()
        return _file_locks[path_str]


def atomic_write_json(file_path: Path, data: Any, indent: int = 2) -> None:
    """
    Atomically write JSON data to a file using temp file + rename.
    
    This prevents corruption if the process crashes during write.
    Uses thread-safe locking if accessed concurrently.
    
    Args:
        file_path: Destination file path
        data: Data to serialize as JSON
        indent: JSON indentation (default 2)
    
    Raises:
        IOError: If write operation fails
        ValueError: If data cannot be serialized to JSON
    """
    lock = _get_file_lock(file_path)
    
    with lock:
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to temporary file first
        tmp_path = file_path.with_suffix(file_path.suffix + '.tmp')
        
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
                f.flush()  # Ensure data is written to disk
            
            # Atomic rename (on POSIX systems)
            tmp_path.replace(file_path)
            logger.debug(f"Atomically wrote JSON to {file_path}")
            
        except Exception as e:
            # Clean up temp file on error
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
            logger.error(f"Failed to write JSON to {file_path}: {e}")
            raise


def read_json(file_path: Path, default: Any = None) -> Any:
    """
    Thread-safe read of JSON file.
    
    Args:
        file_path: Path to JSON file
        default: Default value if file doesn't exist
    
    Returns:
        Parsed JSON data or default value
    
    Raises:
        json.JSONDecodeError: If file contains invalid JSON
        IOError: If file cannot be read
    """
    lock = _get_file_lock(file_path)
    
    with lock:
        if not file_path.exists():
            return default
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
