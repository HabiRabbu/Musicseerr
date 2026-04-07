import asyncio
import logging
import threading
from typing import ClassVar

logger = logging.getLogger(__name__)


class TaskRegistry:
    _instance: ClassVar["TaskRegistry | None"] = None
    _instance_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "TaskRegistry":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, name: str, task: asyncio.Task) -> asyncio.Task:
        with self._lock:
            existing = self._tasks.get(name)
            if existing is not None and not existing.done():
                raise RuntimeError(f"Task '{name}' is already running")
            self._tasks[name] = task
            task.add_done_callback(lambda _t, _name=name: self._auto_unregister(_name, _t))
        return task

    def _auto_unregister(self, name: str, task: asyncio.Task) -> None:
        with self._lock:
            if self._tasks.get(name) is task:
                del self._tasks[name]

    def unregister(self, name: str) -> None:
        with self._lock:
            self._tasks.pop(name, None)

    async def cancel(self, name: str, grace_period: float = 10.0) -> None:
        with self._lock:
            task = self._tasks.pop(name, None)

        if task is None or task.done():
            return

        task.cancel()
        try:
            await asyncio.wait_for(task, timeout=grace_period)
        except asyncio.CancelledError:
            return
        except asyncio.TimeoutError:
            logger.warning("Task '%s' did not finish within grace period", name)

    async def cancel_all(self, grace_period: float = 10.0) -> None:
        with self._lock:
            tasks = dict(self._tasks)
            self._tasks.clear()

        if not tasks:
            return

        for name, task in tasks.items():
            if not task.done():
                task.cancel()

        done, pending = await asyncio.wait(
            tasks.values(), timeout=grace_period, return_when=asyncio.ALL_COMPLETED
        )

        for name, task in tasks.items():
            if task in pending:
                logger.warning("Task '%s' did not finish within grace period", name)

    def get_all(self) -> dict[str, asyncio.Task]:
        with self._lock:
            return dict(self._tasks)

    def is_running(self, name: str) -> bool:
        with self._lock:
            task = self._tasks.get(name)
            return task is not None and not task.done()

    def reset(self) -> None:
        with self._lock:
            self._tasks.clear()
