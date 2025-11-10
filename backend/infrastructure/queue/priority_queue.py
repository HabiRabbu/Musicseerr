import asyncio
import logging
from enum import IntEnum
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class RequestPriority(IntEnum):
    USER_INITIATED = 0
    PREFETCH_VISIBLE = 1
    BACKGROUND_SYNC = 2
    OPPORTUNISTIC = 3


class PriorityQueueManager:
    _instance: Optional['PriorityQueueManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._user_semaphore = asyncio.Semaphore(50)
        self._background_semaphore = asyncio.Semaphore(5)
        self._user_activity_flag = False
        self._user_activity_timestamp = 0.0
        self._user_activity_timeout = 2.0
        self._user_activity_event = asyncio.Event()
        self._background_waiters = 0
        self._initialized = True
        
        logger.info("PriorityQueueManager initialized: user=50, background=5")
    
    async def acquire_slot(self, priority: RequestPriority) -> asyncio.Semaphore:
        if priority == RequestPriority.USER_INITIATED:
            self._mark_user_activity()
            return self._user_semaphore
        else:
            await self._wait_for_user_inactivity()
            return self._background_semaphore
    
    def _mark_user_activity(self):
        self._user_activity_flag = True
        self._user_activity_timestamp = datetime.now().timestamp()
        self._user_activity_event.clear()
    
    async def _wait_for_user_inactivity(self):
        self._background_waiters += 1
        try:
            while self._user_activity_flag:
                current = datetime.now().timestamp()
                elapsed = current - self._user_activity_timestamp
                
                if elapsed >= self._user_activity_timeout:
                    self._user_activity_flag = False
                    self._user_activity_event.set()
                    break
                
                wait_time = self._user_activity_timeout - elapsed
                try:
                    await asyncio.wait_for(
                        self._user_activity_event.wait(),
                        timeout=wait_time + 0.1
                    )
                except asyncio.TimeoutError:
                    pass
        finally:
            self._background_waiters -= 1
    
    def is_user_active(self) -> bool:
        current = datetime.now().timestamp()
        if current - self._user_activity_timestamp > self._user_activity_timeout:
            self._user_activity_flag = False
        return self._user_activity_flag
    
    def get_stats(self) -> dict:
        return {
            'user_slots_available': self._user_semaphore._value,
            'background_slots_available': self._background_semaphore._value,
            'user_active': self.is_user_active(),
            'background_waiters': self._background_waiters
        }


def get_priority_queue() -> PriorityQueueManager:
    return PriorityQueueManager()
