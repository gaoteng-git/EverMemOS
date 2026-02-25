"""
KV-Storage Interface

Interface for key-value storage backends.
Used to store complete model data separately from MongoDB indexes.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Tuple, AsyncIterator


class KVStorageInterface(ABC):
    """Interface for KV-Storage implementations"""

    @abstractmethod
    async def get(self, key: str) -> Optional[str]:
        """
        Get value by key

        Args:
            key: Storage key (usually document ID)

        Returns:
            JSON string or None if not found
        """
        pass

    @abstractmethod
    async def put(self, key: str, value: str) -> bool:
        """
        Store key-value pair

        Args:
            key: Storage key
            value: JSON string to store

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """
        Delete by key

        Args:
            key: Storage key

        Returns:
            True if deleted
        """
        pass

    @abstractmethod
    async def batch_get(self, keys: List[str]) -> Dict[str, str]:
        """
        Batch get values

        Args:
            keys: List of storage keys

        Returns:
            Dict mapping key to JSON string
        """
        pass

    @abstractmethod
    async def batch_delete(self, keys: List[str]) -> int:
        """
        Batch delete keys

        Args:
            keys: List of storage keys

        Returns:
            Number of keys deleted
        """
        pass

    @abstractmethod
    async def iterate_all(self) -> AsyncIterator[Tuple[str, str]]:
        """
        Iterate all key-value pairs in storage

        Used for data validation and recovery (e.g., MongoDB completeness check).
        Empty/deleted entries (empty string values) should be skipped.

        Yields:
            Tuple[str, str]: (key, value_json_string)
            - key: Full key with collection prefix "{collection_name}:{document_id}"
            - value: JSON string of full document data
        """
        # Make this an async generator in the abstract base
        # (required so subclasses can use `yield` without extra boilerplate)
        return
        yield  # noqa: unreachable — makes this an async generator


__all__ = ["KVStorageInterface"]
