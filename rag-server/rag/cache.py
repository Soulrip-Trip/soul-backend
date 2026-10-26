import threading
import time
from collections import OrderedDict
from typing import Any


class TTLCache:
    """프로세스 메모리 LRU + TTL 캐시(스레드 안전).

    동일 질의 재검색과 질의 임베딩 재호출을 막는 용도라 Redis 같은 외부 저장소 없이 충분하다.
    """

    def __init__(self, maxsize: int = 512, ttl: float = 600.0) -> None:
        self.maxsize = maxsize
        self.ttl = ttl
        self._data: OrderedDict[Any, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: Any) -> Any | None:
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

    def set(self, key: Any, value: Any) -> None:
        if self.ttl <= 0:
            return
        with self._lock:
            self._data[key] = (time.monotonic() + self.ttl, value)
            self._data.move_to_end(key)
            while len(self._data) > self.maxsize:
                self._data.popitem(last=False)

    def stats(self) -> dict:
        return {"size": len(self._data), "hits": self.hits, "misses": self.misses, "ttl": self.ttl}
