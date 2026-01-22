"""
Milvus Dual Storage Collection Proxy

Elegant interception solution for Milvus dual storage:
- Intercepts AsyncCollection calls to automatically implement dual storage
- Milvus stores Lite data (vector + index fields + metadata)
- KV-Storage stores Full data (complete entity dict)
- Zero changes to Repository code
- Compatible with future updates

Working principle:
1. Wrap AsyncCollection.insert/upsert to sync to KV
2. Milvus stores Lite fields, KV stores Full dict
3. Query methods return Lite data (metadata contains most info)
4. Optional: load Full data from KV when needed

Usage:
    class EpisodicMemoryMilvusRepository(
        MilvusDualStorageMixin,  # Just add Mixin
        BaseMilvusRepository[EpisodicMemoryCollection]
    ):
        # All code remains unchanged
        pass
"""

import json
from typing import Dict, Any, List, Optional, Set
from functools import wraps

from core.observation.logger import get_logger
from core.oxm.milvus.async_collection import AsyncCollection

logger = get_logger(__name__)


class MilvusCollectionProxy:
    """
    Milvus Collection Proxy - Automatic dual storage implementation

    Intercepts AsyncCollection method calls:
    - insert(): Write Lite to Milvus, Full to KV
    - upsert(): Write Lite to Milvus, Full to KV
    - search(): Return Lite data directly
    - query(): Return Lite data directly
    - delete(): Delete from both Milvus and KV

    Design philosophy:
    - Milvus stores: vector + index fields + metadata (JSON, max 50KB)
    - KV stores: complete entity dict for future extensibility
    - Metadata field contains most necessary info (user_name, title, summary, etc.)
    - Query returns Lite data (sufficient for most scenarios)
    """

    def __init__(
        self,
        original_collection: AsyncCollection,
        kv_storage: 'KVStorageInterface',
        collection_name: str,
        lite_fields: Optional[Set[str]] = None,
    ):
        """
        Initialize proxy

        Args:
            original_collection: Original AsyncCollection instance
            kv_storage: KV-Storage instance
            collection_name: Milvus collection name (for KV key generation)
            lite_fields: Fields to keep in Milvus (if None, keep all fields)
                        Typically: {id, vector, user_id, group_id, event_type,
                                   timestamp, episode, search_content, metadata,
                                   parent_type, parent_id, created_at, updated_at}
        """
        self._original_collection = original_collection
        self._kv_storage = kv_storage
        self._collection_name = collection_name
        self._lite_fields = lite_fields or self._default_lite_fields()

        logger.debug(
            f"✅ MilvusCollectionProxy initialized for {collection_name}, "
            f"lite_fields count: {len(self._lite_fields)}"
        )

    @staticmethod
    def _default_lite_fields() -> Set[str]:
        """
        Default Lite fields to keep in Milvus

        Includes:
        - Required: id, vector (for vector search)
        - Index fields: user_id, group_id, event_type, timestamp, parent_id
        - Content fields: episode, search_content, metadata
        - Audit fields: created_at, updated_at
        """
        return {
            # Required fields
            "id",
            "vector",
            # Index fields
            "user_id",
            "group_id",
            "event_type",
            "timestamp",
            "parent_type",
            "parent_id",
            # Content fields
            "episode",  # or "atomic_fact" for EventLog, "content" for Foresight
            "search_content",
            "metadata",
            # Audit fields
            "created_at",
            "updated_at",
            # Array fields
            "participants",
            # Foresight-specific
            "start_time",
            "end_time",
            "duration_days",
            "evidence",
            # EventLog-specific
            "atomic_fact",
            # Foresight-specific
            "content",
        }

    def _extract_lite_data(self, full_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract Lite fields from Full data

        Strategy:
        1. For lite fields: copy actual values from full_data
        2. For non-lite fields that exist in full_data: provide minimal/empty values to save Milvus storage
           - This satisfies Milvus schema requirements (all fields must be present)
           - But minimizes storage usage for non-indexed, non-queried fields
           - Full data is preserved in KV-Storage

        Args:
            full_data: Complete entity dict

        Returns:
            Lite entity dict with actual values for lite fields, empty values for non-lite fields
        """
        if not self._lite_fields:
            # If no lite_fields specified, keep all data
            return full_data

        lite_data = {}

        # Process all fields in full_data
        for field, value in full_data.items():
            if field in self._lite_fields:
                # Lite field: copy actual value
                lite_data[field] = value
            else:
                # Non-lite field: provide minimal/empty value to satisfy Milvus schema
                # while saving storage space
                lite_data[field] = self._get_empty_value_for_field(field, value)

        return lite_data

    def _get_empty_value_for_field(self, field_name: str, original_value: Any) -> Any:
        """
        Get minimal/empty value for a non-lite field to save Milvus storage

        Args:
            field_name: Name of the field
            original_value: Original value (used to infer type)

        Returns:
            Minimal value appropriate for the field type
        """
        # For string fields, return empty string
        if isinstance(original_value, str):
            return ""

        # For numeric fields, return 0
        if isinstance(original_value, (int, float)):
            return 0

        # For list/array fields, return empty list
        if isinstance(original_value, list):
            return []

        # For dict fields, return empty dict
        if isinstance(original_value, dict):
            return {}

        # For None or unknown types, return the original value
        return original_value

    def _get_kv_key(self, doc_id: str) -> str:
        """
        Generate KV-Storage key

        Format: milvus:{collection_name}:{doc_id}
        Example: milvus:episodic_memory:507f1f77bcf86cd799439011
        """
        return f"milvus:{self._collection_name}:{doc_id}"

    async def _sync_to_kv(self, full_data: Dict[str, Any]) -> bool:
        """
        Sync Full data to KV-Storage

        Args:
            full_data: Complete entity dict

        Returns:
            Success status
        """
        try:
            doc_id = full_data.get("id")
            if not doc_id:
                logger.warning("⚠️  Cannot sync to KV: missing 'id' field")
                return False

            kv_key = self._get_kv_key(doc_id)
            kv_value = json.dumps(full_data, ensure_ascii=False)

            await self._kv_storage.put(kv_key, kv_value)
            logger.debug(f"✅ Synced to KV: {kv_key}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to sync to KV: {e}", exc_info=True)
            return False

    async def _delete_from_kv(self, doc_id: str) -> bool:
        """
        Delete data from KV-Storage

        Args:
            doc_id: Document ID

        Returns:
            Success status
        """
        try:
            kv_key = self._get_kv_key(doc_id)
            await self._kv_storage.delete(kv_key)
            logger.debug(f"✅ Deleted from KV: {kv_key}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to delete from KV: {e}", exc_info=True)
            return False

    # ==================== Intercepted Write Methods ====================

    async def insert(
        self,
        data: Any,
        partition_name: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        """
        Insert data - Automatic dual storage

        Process:
        1. Extract Lite data (vector + index fields + metadata)
        2. Write Lite to Milvus
        3. Write Full to KV-Storage (async, don't block on failure)

        Args:
            data: Entity dict or list of entity dicts
            partition_name: Partition name
            timeout: Timeout in seconds

        Returns:
            Insert result (from Milvus)
        """
        try:
            # Handle single entity or list
            if isinstance(data, dict):
                # Single entity
                lite_data = self._extract_lite_data(data)
                result = await self._original_collection.insert(
                    lite_data, partition_name, timeout
                )
                # Sync Full data to KV (don't block on failure)
                await self._sync_to_kv(data)
                return result

            elif isinstance(data, list):
                # Batch entities
                lite_data_list = [self._extract_lite_data(d) for d in data]
                result = await self._original_collection.insert(
                    lite_data_list, partition_name, timeout
                )
                # Sync all Full data to KV
                for d in data:
                    await self._sync_to_kv(d)
                return result

            else:
                # Unknown format, pass through
                return await self._original_collection.insert(
                    data, partition_name, timeout
                )

        except Exception as e:
            logger.error(f"❌ Milvus insert failed: {e}", exc_info=True)
            raise

    async def upsert(
        self,
        data: Any,
        partition_name: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        """
        Upsert data - Automatic dual storage

        Similar to insert(), extracts Lite data for Milvus and syncs Full to KV
        """
        try:
            # Handle single entity or list
            if isinstance(data, dict):
                lite_data = self._extract_lite_data(data)
                result = await self._original_collection.upsert(
                    lite_data, partition_name, timeout
                )
                await self._sync_to_kv(data)
                return result

            elif isinstance(data, list):
                lite_data_list = [self._extract_lite_data(d) for d in data]
                result = await self._original_collection.upsert(
                    lite_data_list, partition_name, timeout
                )
                for d in data:
                    await self._sync_to_kv(d)
                return result

            else:
                return await self._original_collection.upsert(
                    data, partition_name, timeout
                )

        except Exception as e:
            logger.error(f"❌ Milvus upsert failed: {e}", exc_info=True)
            raise

    async def delete(
        self,
        expr: str,
        partition_name: Optional[str] = None,
    ):
        """
        Delete data - Also delete from KV

        Process:
        1. Query IDs to delete
        2. Delete from Milvus
        3. Delete from KV-Storage (best effort)
        """
        try:
            # First query IDs to delete
            results = await self._original_collection.query(
                expr=expr,
                output_fields=["id"],
                partition_names=[partition_name] if partition_name else None,
            )

            # Delete from Milvus
            delete_result = await self._original_collection.delete(expr, partition_name)

            # Delete from KV (best effort, don't fail if KV delete fails)
            if results:
                for result in results:
                    doc_id = result.get("id")
                    if doc_id:
                        await self._delete_from_kv(doc_id)

            return delete_result

        except Exception as e:
            logger.error(f"❌ Milvus delete failed: {e}", exc_info=True)
            raise

    # ==================== Enhanced Read Methods ====================

    async def search(self, *args, **kwargs):
        """
        Search - Automatically load Full data from KV

        Process:
        1. Milvus search returns Lite data with IDs
        2. Batch load Full data from KV by IDs
        3. Merge Full data into search results
        4. Return complete results (user unaware of KV layer)
        """
        # Get Lite results from Milvus
        lite_results = await self._original_collection.search(*args, **kwargs)

        # Auto-load Full data from KV
        enhanced_results = await self._enhance_search_results_with_kv(lite_results)

        return enhanced_results

    async def query(self, *args, **kwargs):
        """
        Query - Automatically load Full data from KV

        Similar to search(), auto-enhances results with Full data
        """
        # Get Lite results from Milvus
        lite_results = await self._original_collection.query(*args, **kwargs)

        # Auto-load Full data from KV
        enhanced_results = await self._enhance_query_results_with_kv(lite_results)

        return enhanced_results

    async def _enhance_search_results_with_kv(self, search_results):
        """
        Enhance Milvus search results with Full data from KV

        Args:
            search_results: Milvus search results (list of hits)

        Returns:
            Enhanced results with Full data merged
        """
        try:
            if not search_results:
                return search_results

            # Extract all doc IDs from search results
            doc_ids = []
            for hits in search_results:
                for hit in hits:
                    doc_id = hit.entity.get("id")
                    if doc_id:
                        doc_ids.append(doc_id)

            if not doc_ids:
                logger.debug("No doc IDs found in search results, returning Lite data")
                return search_results

            # Batch load Full data from KV
            kv_keys = [self._get_kv_key(doc_id) for doc_id in doc_ids]
            full_data_map = await self._batch_load_from_kv(kv_keys, doc_ids)

            # Merge Full data into search results
            for hits in search_results:
                for hit in hits:
                    doc_id = hit.entity.get("id")
                    if doc_id and doc_id in full_data_map:
                        # Merge Full data into hit.entity
                        full_data = full_data_map[doc_id]
                        hit.entity.update(full_data)

            logger.debug(
                f"✅ Enhanced search results: loaded {len(full_data_map)}/{len(doc_ids)} Full data from KV"
            )

            return search_results

        except Exception as e:
            logger.warning(
                f"⚠️  Failed to enhance search results with KV data: {e}, returning Lite data",
                exc_info=True
            )
            # Fallback: return Lite data on error
            return search_results

    async def _enhance_query_results_with_kv(self, query_results):
        """
        Enhance Milvus query results with Full data from KV

        Args:
            query_results: Milvus query results (list of dicts)

        Returns:
            Enhanced results with Full data merged
        """
        try:
            if not query_results:
                return query_results

            # Extract doc IDs
            doc_ids = [result.get("id") for result in query_results if result.get("id")]

            if not doc_ids:
                logger.debug("No doc IDs found in query results, returning Lite data")
                return query_results

            # Batch load Full data from KV
            kv_keys = [self._get_kv_key(doc_id) for doc_id in doc_ids]
            full_data_map = await self._batch_load_from_kv(kv_keys, doc_ids)

            # Merge Full data into query results
            for result in query_results:
                doc_id = result.get("id")
                if doc_id and doc_id in full_data_map:
                    full_data = full_data_map[doc_id]
                    result.update(full_data)

            logger.debug(
                f"✅ Enhanced query results: loaded {len(full_data_map)}/{len(doc_ids)} Full data from KV"
            )

            return query_results

        except Exception as e:
            logger.warning(
                f"⚠️  Failed to enhance query results with KV data: {e}, returning Lite data",
                exc_info=True
            )
            # Fallback: return Lite data on error
            return query_results

    async def _batch_load_from_kv(self, kv_keys: list, doc_ids: list) -> dict:
        """
        Batch load Full data from KV-Storage

        Args:
            kv_keys: List of KV keys
            doc_ids: List of document IDs (same order as kv_keys)

        Returns:
            Dict mapping doc_id to full_data
        """
        try:
            # Use batch_get if available, otherwise fallback to sequential get
            if hasattr(self._kv_storage, 'batch_get'):
                kv_values = await self._kv_storage.batch_get(kv_keys)

                # Parse JSON values
                full_data_map = {}
                for doc_id, kv_key in zip(doc_ids, kv_keys):
                    kv_value = kv_values.get(kv_key)
                    if kv_value:
                        try:
                            full_data = json.loads(kv_value)
                            full_data_map[doc_id] = full_data
                        except Exception as e:
                            logger.warning(f"Failed to parse KV value for {doc_id}: {e}")

                return full_data_map
            else:
                # Fallback: sequential get
                full_data_map = {}
                for doc_id, kv_key in zip(doc_ids, kv_keys):
                    kv_value = await self._kv_storage.get(kv_key)
                    if kv_value:
                        try:
                            full_data = json.loads(kv_value)
                            full_data_map[doc_id] = full_data
                        except Exception as e:
                            logger.warning(f"Failed to parse KV value for {doc_id}: {e}")

                return full_data_map

        except Exception as e:
            logger.error(f"❌ Batch load from KV failed: {e}", exc_info=True)
            return {}

    async def flush(self, *args, **kwargs):
        """Flush - Pass through"""
        return await self._original_collection.flush(*args, **kwargs)

    async def load(self, *args, **kwargs):
        """Load - Pass through"""
        return await self._original_collection.load(*args, **kwargs)

    async def release(self, *args, **kwargs):
        """Release - Pass through"""
        return await self._original_collection.release(*args, **kwargs)

    # ==================== Property Pass-through ====================

    @property
    def collection(self):
        """Pass through collection property"""
        return self._original_collection.collection

    def __getattr__(self, name):
        """
        Forward unknown attributes to original collection

        Ensures compatibility with future AsyncCollection methods
        """
        return getattr(self._original_collection, name)


# Export
__all__ = ["MilvusCollectionProxy"]
