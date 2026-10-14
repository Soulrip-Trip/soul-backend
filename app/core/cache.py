import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Hashable
from typing import Any, TypeVar

T = TypeVar("T")


class TTLCache:
    """프로세스 메모리 LRU + TTL 캐시(스레드 안전).

    Soulrip은 단일 인스턴스 + SQLite 구조라 Redis 없이 프로세스 캐시로 충분하다.
    워커를 여러 개 띄우면 워커마다 캐시가 따로 생긴다는 점만 유의한다.
    """

    def __init__(self, name: str, maxsize: int = 256, ttl: float = 300.0) -> None:
        self.name = name
        self.maxsize = maxsize
        self.ttl = ttl
        self._data: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: Hashable) -> Any | None:
        with self._lock:
            item = self._data.get(key)
            if item is None or item[0] < time.monotonic():
                if item is not None:
                    del self._data[key]
                self.misses += 1
                return None
            self._data.move_to_end(key)
            self.hits += 1
            return item[1]

    def set(self, key: Hashable, value: Any) -> None:
        if self.ttl <= 0:
            return
        with self._lock:
            self._data[key] = (time.monotonic() + self.ttl, value)
            self._data.move_to_end(key)
            while len(self._data) > self.maxsize:
                self._data.popitem(last=False)

    def get_or_set(self, key: Hashable, factory: Callable[[], T]) -> T:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = factory()
        self.set(key, value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def stats(self) -> dict:
        return {"name": self.name, "size": len(self._data), "hits": self.hits, "misses": self.misses}
