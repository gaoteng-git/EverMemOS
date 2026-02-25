"""
Redis KV-Storage Implementation

Production-ready Redis implementation for cross-process data sharing.
"""

from typing import Optional, Dict, List, Tuple, AsyncIterator
from infra_layer.adapters.out.persistence.kv_storage.kv_storage_interface import (
    KVStorageInterface,
)
from core.di.decorators import component
from core.component.redis_provider import RedisProvider
from core.di import get_bean_by_type
from core.observation.logger import get_logger

logger = get_logger(__name__)


@component("redis_kv_storage")
class RedisKVStorage(KVStorageInterface):
    """
    Redis-based KV-Storage implementation

    Supports cross-process data sharing, suitable for production use.
    Uses RedisProvider from the project for connection management.
    """

    def __init__(self):
        """Initialize Redis KV-Storage"""
        self._redis_provider: Optional[RedisProvider] = None

    async def _get_redis(self):
        """Lazy load Redis connection"""
        if self._redis_provider is None:
            try:
                self._redis_provider = get_bean_by_type(RedisProvider)
                logger.info("✅ RedisKVStorage initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to get RedisProvider: {e}")
                raise
        return await self._redis_provider.get_client()

    def _make_key(self, key: str) -> str:
        """Pass through key without modification for consistency with other implementations"""
        return key

    async def get(self, key: str) -> Optional[str]:
        """
        Get value by key

        Args:
            key: Document ID

        Returns:
            JSON string or None if not found
        """
        try:
            redis = await self._get_redis()
            full_key = self._make_key(key)
            value = await redis.get(full_key)

            if value is None:
                return None

            # Redis returns bytes, decode to string
            if isinstance(value, bytes):
                return value.decode('utf-8')
            return value

        except Exception as e:
            logger.error(f"❌ Redis GET failed for key {key}: {e}")
            return None

    async def put(self, key: str, value: str) -> bool:
        """
        Store key-value pair

        Args:
            key: Document ID
            value: JSON string (full document data)

        Returns:
            Success status
        """
        try:
            redis = await self._get_redis()
            full_key = self._make_key(key)

            # Store with no expiration (persistent storage)
            await redis.set(full_key, value)

            logger.debug(f"💾 Redis PUT: {key} ({len(value)} bytes)")
            return True

        except Exception as e:
            logger.error(f"❌ Redis PUT failed for key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete by key

        Args:
            key: Document ID

        Returns:
            Success status (True if deleted, False if not found)
        """
        try:
            redis = await self._get_redis()
            full_key = self._make_key(key)

            result = await redis.delete(full_key)
            return result > 0

        except Exception as e:
            logger.error(f"❌ Redis DELETE failed for key {key}: {e}")
            return False

    async def batch_get(self, keys: List[str]) -> Dict[str, str]:
        """
        Batch get values

        Args:
            keys: List of document IDs

        Returns:
            Dict mapping keys to values (only includes found keys)
        """
        if not keys:
            return {}

        try:
            redis = await self._get_redis()
            full_keys = [self._make_key(k) for k in keys]

            # Use Redis MGET for batch retrieval
            values = await redis.mget(full_keys)

            result = {}
            for key, value in zip(keys, values):
                if value is not None:
                    # Decode bytes to string
                    if isinstance(value, bytes):
                        value = value.decode('utf-8')
                    result[key] = value

            return result

        except Exception as e:
            logger.error(f"❌ Redis BATCH_GET failed: {e}")
            return {}

    async def batch_delete(self, keys: List[str]) -> int:
        """
        Batch delete keys

        Args:
            keys: List of document IDs

        Returns:
            Number of keys deleted
        """
        if not keys:
            return 0

        try:
            redis = await self._get_redis()
            full_keys = [self._make_key(k) for k in keys]

            # Use Redis DEL for batch deletion
            count = await redis.delete(*full_keys)

            logger.debug(f"🗑️  Redis BATCH_DELETE: deleted {count}/{len(keys)} keys")
            return count

        except Exception as e:
            logger.error(f"❌ Redis BATCH_DELETE failed: {e}")
            return 0

    async def iterate_all(self) -> AsyncIterator[Tuple[str, str]]:
        """
        Iterate all key-value pairs using Redis SCAN.

        Uses cursor-based SCAN to avoid blocking Redis on large datasets.
        """
        try:
            redis = await self._get_redis()
            cursor = 0
            total_count = 0

            while True:
                cursor, keys = await redis.scan(cursor=cursor, count=100)

                if keys:
                    str_keys = [k.decode('utf-8') if isinstance(k, bytes) else k for k in keys]
                    values = await redis.mget(str_keys)

                    for key, value in zip(str_keys, values):
                        if value is not None:
                            if isinstance(value, bytes):
                                value = value.decode('utf-8')
                            total_count += 1
                            yield (key, value)

                if cursor == 0:
                    break

            logger.debug(f"✅ Redis iterate_all completed: {total_count} key-value pairs")

        except Exception as e:
            logger.error(f"❌ Redis iterate_all failed: {e}")
            raise


__all__ = ["RedisKVStorage"]
