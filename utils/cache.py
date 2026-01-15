# utils/cache.py
from datetime import datetime, timedelta
from typing import Any, Optional
import asyncio


class SimpleCache:
    """Oddiy va tezkor keshlash"""

    def __init__(self):
        self._cache = {}
        self._lock = asyncio.Lock()

    async def set(self, key: str, value: Any, ttl: int = 3600):
        """Keshga saqlash (ttl - soniyada, default 1 soat)"""
        async with self._lock:
            expire_time = datetime.now() + timedelta(seconds=ttl)
            self._cache[key] = {
                'value': value,
                'expire': expire_time
            }

    async def get(self, key: str) -> Optional[Any]:
        """Keshdan olish"""
        async with self._lock:
            data = self._cache.get(key)

            if not data:
                return None

            # Vaqti o'tganmi?
            if datetime.now() > data['expire']:
                del self._cache[key]  # O'chirish
                return None

            return data['value']

    async def delete(self, key: str):
        """O'chirish"""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]

    async def clear_expired(self):
        """Vaqti o'tganlarni tozalash"""
        async with self._lock:
            now = datetime.now()
            expired_keys = [
                key for key, data in self._cache.items()
                if now > data['expire']
            ]

            for key in expired_keys:
                del self._cache[key]

    def get_stats(self):
        """Statistika"""
        return {
            'total': len(self._cache),
            'keys': list(self._cache.keys())
        }


# Global cache instance
cache = SimpleCache()