import asyncio
import json
import logging
import threading
from pathlib import Path
from typing import Any

import aiofiles
import aiofiles.os

logger = logging.getLogger(__name__)

_file_locks: dict[str, threading.Lock] = {}
_locks_lock = threading.Lock()
_async_locks: dict[str, asyncio.Lock] = {}


def _get_file_lock(file_path: Path) -> threading.Lock:
    path_str = str(file_path.resolve())
    with _locks_lock:
        if path_str not in _file_locks:
            _file_locks[path_str] = threading.Lock()
        return _file_locks[path_str]


def _get_async_lock(file_path: Path) -> asyncio.Lock:
    path_str = str(file_path.resolve())
    if path_str not in _async_locks:
        _async_locks[path_str] = asyncio.Lock()
    return _async_locks[path_str]


def atomic_write_json(file_path: Path, data: Any, indent: int = 2) -> None:
    lock = _get_file_lock(file_path)
    
    with lock:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = file_path.with_suffix(file_path.suffix + '.tmp')
        
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
                f.flush()
            
            tmp_path.replace(file_path)
            logger.debug(f"Atomically wrote JSON to {file_path}")
            
        except Exception as e:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
            logger.error(f"Failed to write JSON to {file_path}: {e}")
            raise


async def atomic_write_json_async(file_path: Path, data: Any, indent: int = 2) -> None:
    lock = _get_async_lock(file_path)
    
    async with lock:
        await aiofiles.os.makedirs(file_path.parent, exist_ok=True)
        tmp_path = file_path.with_suffix(file_path.suffix + '.tmp')
        
        try:
            content = json.dumps(data, indent=indent, ensure_ascii=False)
            async with aiofiles.open(tmp_path, 'w', encoding='utf-8') as f:
                await f.write(content)
            
            await asyncio.to_thread(tmp_path.replace, file_path)
            logger.debug(f"Atomically wrote JSON to {file_path}")
            
        except Exception as e:
            try:
                if tmp_path.exists():
                    await aiofiles.os.remove(tmp_path)
            except Exception:
                pass
            logger.error(f"Failed to write JSON to {file_path}: {e}")
            raise


def read_json(file_path: Path, default: Any = None) -> Any:
    lock = _get_file_lock(file_path)
    
    with lock:
        if not file_path.exists():
            return default
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)


async def read_json_async(file_path: Path, default: Any = None) -> Any:
    lock = _get_async_lock(file_path)
    
    async with lock:
        if not file_path.exists():
            return default
        
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            return json.loads(content)
