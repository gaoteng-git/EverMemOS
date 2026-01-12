"""
MemCell Native CRUD Repository

Native data access layer for MemCell based on Beanie ODM, providing complete CRUD operations.
Supports dual-storage architecture with configurable storage modes:
- FULL mode: MongoDB stores all fields, KV-Storage validation enabled
- LITE mode: MongoDB stores only indexed fields, full data in KV-Storage

Does not depend on domain layer interfaces, directly operates on MemCell document models.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Type, Union
from bson import ObjectId
from pydantic import BaseModel
from beanie.operators import And, GTE, LT, Eq, RegEx, Or
from pymongo.asynchronous.client_session import AsyncClientSession
from core.observation.logger import get_logger
from core.di.decorators import repository
from core.di import get_bean_by_type
from core.oxm.mongo.base_repository import BaseRepository

from infra_layer.adapters.out.persistence.document.memory.memcell import (
    MemCell,
    DataTypeEnum,
)
from infra_layer.adapters.out.persistence.document.memory.memcell_lite import (
    MemCellLite,
)
from infra_layer.adapters.out.persistence.kv_storage import (
    MemCellKVStorage,
    compare_memcell_data,
    log_inconsistency,
)
from infra_layer.adapters.out.persistence.kv_storage.storage_config import (
    is_full_storage_mode,
    should_validate_kv_consistency,
    get_storage_config,
)

logger = get_logger(__name__)


@repository("memcell_raw_repository", primary=True)
class MemCellRawRepository(BaseRepository[MemCell]):
    """
    MemCell Native CRUD Repository

    Provides direct database operations on MemCell documents, including:
    - Basic CRUD operations (inherited from BaseRepository)
    - Composite queries and filtering
    - Batch operations
    - Statistics and aggregation queries
    - Transaction management (inherited from BaseRepository)

    Supports dual-storage modes:
    - FULL: MongoDB stores all fields, KV validation enabled
    - LITE: MongoDB stores only indexed fields, full data in KV-Storage
    """

    def __init__(self):
        """Initialize repository with KV-Storage support and storage mode detection"""
        # Initialize with MemCell model (full) by default
        # Actual model used for queries determined by storage mode
        super().__init__(MemCell)

        # Storage configuration
        self._storage_config = get_storage_config()
        logger.info(f"📦 MemCell Storage Mode: {self._storage_config}")

        # Inject KV-Storage with graceful degradation
        self._kv_storage: Optional[MemCellKVStorage] = None
        try:
            self._kv_storage = get_bean_by_type(MemCellKVStorage)
            logger.info("✅ MemCell KV-Storage initialized successfully")
        except Exception as e:
            logger.warning(
                f"⚠️  MemCell KV-Storage not available: {e}. "
                "Repository will operate in MongoDB-only mode."
            )

    def _get_mongo_model(self) -> Union[Type[MemCell], Type[MemCellLite]]:
        """
        Get appropriate MongoDB model based on storage mode

        Returns:
            MemCell: Full model (FULL mode)
            MemCellLite: Lite model with only indexed fields (LITE mode)
        """
        if is_full_storage_mode():
            return MemCell
        else:
            return MemCellLite

    def _get_kv_storage(self) -> Optional[MemCellKVStorage]:
        """
        Get KV-Storage instance with availability check.

        Returns:
            KV-Storage instance if available, None otherwise
        """
        if self._kv_storage is None:
            logger.debug("KV-Storage not available, skipping KV operations")
        return self._kv_storage

    def _memcell_to_lite(self, memcell: MemCell) -> MemCellLite:
        """
        Convert full MemCell to MemCellLite (only indexed fields)

        Args:
            memcell: Full MemCell instance

        Returns:
            MemCellLite instance with only indexed/query fields
        """
        return MemCellLite(
            id=memcell.id,
            user_id=memcell.user_id,
            timestamp=memcell.timestamp,
            group_id=memcell.group_id,
            participants=memcell.participants,
            type=memcell.type,
            keywords=memcell.keywords,
            created_at=memcell.created_at,
            updated_at=memcell.updated_at,
        )

    async def _reconstruct_from_kv(
        self, mongo_doc: Union[MemCell, MemCellLite], event_id: str
    ) -> Optional[MemCell]:
        """
        Reconstruct full MemCell from KV-Storage data

        Args:
            mongo_doc: MongoDB document (lite or full)
            event_id: Event ID for KV-Storage lookup

        Returns:
            Full MemCell instance from KV-Storage, or None if not found
        """
        kv_storage = self._get_kv_storage()
        if not kv_storage:
            logger.warning(f"KV-Storage unavailable, cannot reconstruct MemCell: {event_id}")
            # Fallback: if mongo_doc is already full MemCell, return it
            if isinstance(mongo_doc, MemCell):
                return mongo_doc
            return None

        try:
            kv_json = await kv_storage.get(key=event_id)
            if not kv_json:
                logger.warning(f"MemCell not found in KV-Storage: {event_id}")
                return None

            # Deserialize full MemCell from KV-Storage
            full_memcell = MemCell.model_validate_json(kv_json)
            logger.debug(f"✅ Reconstructed full MemCell from KV-Storage: {event_id}")
            return full_memcell

        except Exception as e:
            logger.error(f"Failed to reconstruct MemCell from KV-Storage: {event_id}, error: {e}")
            return None

    async def _process_query_results(
        self, results: List[Union[MemCell, MemCellLite]]
    ) -> List[MemCell]:
        """
        Process query results - ALWAYS reconstruct from KV-Storage

        MongoDB is only used for querying and getting _id list.
        Actual data MUST be read from KV-Storage regardless of storage mode.

        Args:
            results: List of MongoDB query results (lite or full, only for _id)

        Returns:
            List of full MemCell instances from KV-Storage
        """
        if not results:
            return []

        # Get KV-Storage instance
        kv_storage = self._get_kv_storage()
        if not kv_storage:
            logger.error("❌ KV-Storage unavailable, cannot reconstruct MemCells")
            return []

        # Extract event IDs from MongoDB results
        kv_keys = [str(r.id) for r in results]

        # Batch get from KV-Storage (this is the source of truth)
        kv_data_dict = await kv_storage.batch_get(keys=kv_keys)

        # Reconstruct full MemCells from KV-Storage
        full_memcells = []
        for result in results:
            event_id = str(result.id)
            kv_json = kv_data_dict.get(event_id)
            if kv_json:
                try:
                    full_memcell = MemCell.model_validate_json(kv_json)
                    full_memcells.append(full_memcell)
                except Exception as e:
                    logger.error(f"❌ Failed to deserialize MemCell from KV: {event_id}, error: {e}")
            else:
                logger.warning(f"⚠️  MemCell not found in KV-Storage: {event_id}")

        logger.debug(
            f"✅ Reconstructed {len(full_memcells)}/{len(results)} MemCells from KV-Storage "
            f"(mode: {'FULL' if is_full_storage_mode() else 'LITE'})"
        )

        # Optional: Validate consistency in FULL mode
        if is_full_storage_mode() and should_validate_kv_consistency():
            await self._compare_results_with_kv(results, kv_data_dict)

        return full_memcells

    async def _batch_get_from_kv(self, results: List[MemCell]) -> Dict[str, str]:
        """
        Batch get MemCell data from KV-Storage.

        Args:
            results: List of MemCell instances from MongoDB

        Returns:
            Dictionary mapping event_id to JSON string from KV-Storage.
            Returns empty dict if KV-Storage unavailable or on error.
        """
        if not results:
            return {}

        kv_storage = self._get_kv_storage()
        if not kv_storage:
            return {}

        try:
            # Extract event IDs and batch get from KV-Storage
            kv_keys = [str(mc.id) for mc in results]
            kv_data_dict = await kv_storage.batch_get(keys=kv_keys)
            return kv_data_dict
        except Exception as kv_error:
            logger.warning(f"⚠️  KV batch get failed: {kv_error}", exc_info=True)
            return {}

    async def _compare_results_with_kv(
        self, results: List[MemCell], kv_data_dict: Dict[str, str]
    ) -> None:
        """
        Compare MongoDB results with KV-Storage data and log inconsistencies.
        Only performs validation in FULL storage mode.

        Args:
            results: List of MemCell instances from MongoDB
            kv_data_dict: Dictionary of KV-Storage data (event_id -> JSON string)
        """
        # Skip validation in LITE mode
        if not should_validate_kv_consistency():
            logger.debug("KV-Storage validation skipped (LITE mode)")
            return

        if not results or not kv_data_dict:
            return

        for result in results:
            event_id = str(result.id)
            if event_id in kv_data_dict:
                # Serialize MongoDB data for comparison
                mongo_json = result.model_dump_json(by_alias=True, exclude_none=False)
                kv_json = kv_data_dict[event_id]

                # Compare for consistency
                is_consistent, diff_desc = compare_memcell_data(mongo_json, kv_json)

                if not is_consistent:
                    logger.error(f"❌ Data inconsistency for {event_id}: {diff_desc}")
                    log_inconsistency(event_id, {"difference": diff_desc})
                else:
                    logger.debug(f"✅ KV-Storage validation passed: {event_id}")
            else:
                logger.warning(f"⚠️  KV-Storage data missing: {event_id}")

    async def get_by_event_id(self, event_id: str) -> Optional[MemCell]:
        """
        Get MemCell by event_id - ALWAYS returns data from KV-Storage

        MongoDB is only used for querying to verify record exists.
        Actual data MUST be read from KV-Storage regardless of storage mode.

        Args:
            event_id: Event ID

        Returns:
            Full MemCell instance from KV-Storage, or None
        """
        try:
            # Get appropriate model based on storage mode
            mongo_model = self._get_mongo_model()

            # 1. Query MongoDB (only to verify record exists and get _id)
            result = await mongo_model.find_one({"_id": ObjectId(event_id)})
            if not result:
                logger.debug("⚠️  MemCell not found in MongoDB: event_id=%s", event_id)
                return None

            logger.debug("✅ MemCell found in MongoDB: %s", event_id)

            # 2. Get KV-Storage instance
            kv_storage = self._get_kv_storage()
            if not kv_storage:
                logger.error("❌ KV-Storage unavailable, cannot retrieve MemCell: %s", event_id)
                return None

            # 3. Read from KV-Storage (source of truth)
            try:
                kv_json = await kv_storage.get(key=event_id)
                if not kv_json:
                    logger.error(f"❌ MemCell not found in KV-Storage: {event_id}")
                    return None

                # Deserialize full MemCell from KV-Storage
                full_memcell = MemCell.model_validate_json(kv_json)
                logger.debug(
                    f"✅ Retrieved MemCell from KV-Storage: {event_id} "
                    f"(mode: {'FULL' if is_full_storage_mode() else 'LITE'})"
                )

                # Optional: Validate consistency in FULL mode
                if is_full_storage_mode() and should_validate_kv_consistency():
                    try:
                        mongo_json = result.model_dump_json(by_alias=True, exclude_none=False)
                        is_consistent, diff_desc = compare_memcell_data(mongo_json, kv_json)

                        if not is_consistent:
                            logger.error(
                                f"❌ Data inconsistency detected for event_id={event_id}\n"
                                f"Difference: {diff_desc}"
                            )
                            log_inconsistency(event_id, {"difference": diff_desc})
                        else:
                            logger.debug(f"✅ KV-Storage validation passed: {event_id}")
                    except Exception as val_error:
                        logger.warning(
                            f"⚠️  KV-Storage validation failed for {event_id}: {val_error}"
                        )

                return full_memcell

            except Exception as kv_error:
                logger.error(f"❌ Failed to read from KV-Storage: {event_id}, error: {kv_error}")
                return None

        except Exception as e:
            logger.error("❌ Failed to retrieve MemCell by event_id: %s", e)
            return None

    async def get_by_event_ids(
        self, event_ids: List[str], projection_model: Optional[Type[BaseModel]] = None
    ) -> Dict[str, MemCell]:
        """
        Batch get MemCell by event_id list - ALWAYS returns data from KV-Storage

        MongoDB is only used for querying to verify records exist.
        Actual data MUST be read from KV-Storage regardless of storage mode.

        Args:
            event_ids: List of event IDs
            projection_model: Deprecated, ignored (always returns full MemCell from KV-Storage)

        Returns:
            Dict[event_id, MemCell]: Mapping dictionary from event_id to full MemCell
            Unfound event_ids will not appear in the dictionary
        """
        try:
            if not event_ids:
                logger.debug("⚠️  event_ids list is empty, returning empty dictionary")
                return {}

            # Convert event_id list to ObjectId list
            object_ids = []
            valid_event_ids = []
            for event_id in event_ids:
                try:
                    object_ids.append(ObjectId(event_id))
                    valid_event_ids.append(event_id)
                except Exception as e:
                    logger.warning("⚠️  Invalid event_id: %s, error: %s", event_id, e)

            if not object_ids:
                logger.debug("⚠️  No valid event_ids, returning empty dictionary")
                return {}

            # Get appropriate model based on storage mode
            mongo_model = self._get_mongo_model()

            # 1. Query MongoDB (only to verify records exist and get _id list)
            query = mongo_model.find({"_id": {"$in": object_ids}})
            results = await query.to_list()
            logger.debug(f"✅ MongoDB query completed, found {len(results)} records")

            if not results:
                return {}

            # 2. Get KV-Storage instance
            kv_storage = self._get_kv_storage()
            if not kv_storage:
                logger.error("❌ KV-Storage unavailable, cannot retrieve MemCells")
                return {}

            # 3. Batch get from KV-Storage (source of truth)
            kv_keys = [str(r.id) for r in results]
            kv_data_dict = await kv_storage.batch_get(keys=kv_keys)

            # 4. Reconstruct full MemCells from KV-Storage
            result_dict = {}
            for result in results:
                event_id = str(result.id)
                kv_json = kv_data_dict.get(event_id)
                if kv_json:
                    try:
                        full_memcell = MemCell.model_validate_json(kv_json)
                        result_dict[event_id] = full_memcell
                    except Exception as e:
                        logger.error(f"❌ Failed to deserialize MemCell from KV: {event_id}, error: {e}")
                else:
                    logger.warning(f"⚠️  MemCell not found in KV-Storage: {event_id}")

            logger.debug(
                f"✅ Batch retrieved {len(result_dict)}/{len(results)} MemCells from KV-Storage "
                f"(mode: {'FULL' if is_full_storage_mode() else 'LITE'})"
            )

            # Optional: Validate consistency in FULL mode
            if is_full_storage_mode() and should_validate_kv_consistency():
                await self._compare_results_with_kv(results, kv_data_dict)

            return result_dict

        except Exception as e:
            logger.error("❌ Failed to batch retrieve MemCell by event_ids: %s", e)
            return {}

    async def append_memcell(
        self, memcell: MemCell, session: Optional[AsyncClientSession] = None
    ) -> Optional[MemCell]:
        """
        Append MemCell to MongoDB and KV-Storage

        In LITE mode: writes MemCellLite to MongoDB, full MemCell to KV-Storage
        In FULL mode: writes full MemCell to both MongoDB and KV-Storage

        Args:
            memcell: Full MemCell instance to append
            session: Optional MongoDB session for transaction support

        Returns:
            Full MemCell instance with ID populated, or None on failure
        """
        try:
            # 1. Write to MongoDB
            if is_full_storage_mode():
                # FULL mode: write complete MemCell to MongoDB
                await memcell.insert(session=session)
                logger.info(f"✅ MemCell appended (FULL mode): {memcell.event_id}")
            else:
                # LITE mode: write only MemCellLite to MongoDB
                memcell_lite = self._memcell_to_lite(memcell)
                await memcell_lite.insert(session=session)
                # Copy generated ID and audit fields back to full MemCell
                memcell.id = memcell_lite.id
                memcell.created_at = memcell_lite.created_at
                memcell.updated_at = memcell_lite.updated_at
                logger.info(f"✅ MemCell appended (LITE mode): {memcell.event_id}")

            # 2. Write to KV-Storage (always full MemCell)
            kv_storage = self._get_kv_storage()
            if kv_storage:
                try:
                    json_value = memcell.model_dump_json(by_alias=True, exclude_none=False)
                    success = await kv_storage.put(
                        key=str(memcell.id),
                        value=json_value
                    )
                    if success:
                        logger.debug(f"✅ KV-Storage write success: {memcell.event_id}")
                    else:
                        logger.warning(f"⚠️  KV-Storage write failed: {memcell.event_id}")
                except Exception as kv_error:
                    logger.warning(
                        f"⚠️  KV-Storage write error for {memcell.event_id}: {kv_error}",
                        exc_info=True
                    )

            return memcell
        except Exception as e:
            logger.error("❌ Failed to append MemCell: %s", e)
            return None

    async def update_by_event_id(
        self,
        event_id: str,
        update_data: Dict[str, Any],
        session: Optional[AsyncClientSession] = None,
    ) -> Optional[MemCell]:
        """
        Update MemCell by event_id

        Args:
            event_id: Event ID
            update_data: Dictionary of fields to update
            session: Optional MongoDB session

        Returns:
            Updated full MemCell instance or None
        """
        try:
            # 1. Get current MemCell from KV-Storage (for returning updated data)
            memcell = await self.get_by_event_id(event_id)
            if not memcell:
                logger.warning(f"⚠️  MemCell not found for update: {event_id}")
                return None

            # 2. Apply updates to full MemCell
            for key, value in update_data.items():
                if hasattr(memcell, key):
                    setattr(memcell, key, value)

            # 3. Update MongoDB (query fresh document from MongoDB)
            if is_full_storage_mode():
                # FULL mode: query MongoDB document and update it
                mongo_doc = await MemCell.find_one({"_id": ObjectId(event_id)})
                if mongo_doc:
                    # Apply updates to MongoDB document
                    for key, value in update_data.items():
                        if hasattr(mongo_doc, key):
                            setattr(mongo_doc, key, value)
                    await mongo_doc.save(session=session)
                    logger.debug("✅ Updated MemCell in MongoDB (FULL mode)")
            else:
                # LITE mode: update only indexed fields in MongoDB
                memcell_lite = self._memcell_to_lite(memcell)

                # Find and update lite document
                mongo_model = self._get_mongo_model()
                lite_doc = await mongo_model.find_one({"_id": ObjectId(event_id)})
                if lite_doc:
                    # Define indexed fields that can be updated
                    indexed_fields = ['user_id', 'timestamp', 'group_id', 'participants', 'type', 'keywords']

                    # Only update indexed fields that are present in update_data
                    updated_count = 0
                    for field in indexed_fields:
                        if field in update_data:
                            setattr(lite_doc, field, getattr(memcell_lite, field))
                            updated_count += 1

                    # Always update audit timestamp
                    lite_doc.updated_at = memcell.updated_at

                    await lite_doc.save(session=session)
                    logger.debug(f"✅ Updated {updated_count} indexed fields in MongoDB (LITE mode)")

            logger.debug("✅ MemCell updated in MongoDB: %s", event_id)

            # 4. Update KV-Storage (always full MemCell)
            kv_storage = self._get_kv_storage()
            if kv_storage:
                try:
                    json_value = memcell.model_dump_json(by_alias=True, exclude_none=False)
                    await kv_storage.put(key=event_id, value=json_value)
                    logger.debug(f"✅ KV-Storage update success: {event_id}")
                except Exception as kv_error:
                    logger.warning(f"⚠️  KV-Storage update failed: {kv_error}")

            return memcell
        except Exception as e:
            logger.error("❌ Failed to update MemCell: %s", e)
            raise

    async def delete_by_event_id(
        self,
        event_id: str,
        deleted_by: Optional[str] = None,
        session: Optional[AsyncClientSession] = None,
    ) -> bool:
        """
        Soft delete MemCell by event_id

        Args:
            event_id: Event ID
            deleted_by: Deleter (optional)
            session: Optional MongoDB session, for transaction support

        Returns:
            Returns True if deletion succeeds, otherwise False
        """
        try:
            memcell = await self.get_by_event_id(event_id)
            if memcell:
                # 1. Delete from MongoDB (primary operation)
                await memcell.delete(deleted_by=deleted_by, session=session)
                logger.debug(
                    "✅ Successfully soft deleted MemCell by event_id: %s", event_id
                )

                # 2. Delete from KV-Storage (secondary operation)
                kv_storage = self._get_kv_storage()
                if kv_storage:
                    try:
                        success = await kv_storage.delete(key=event_id)
                        if success:
                            logger.debug(f"✅ KV-Storage delete success: {event_id}")
                        else:
                            logger.warning(f"⚠️  KV-Storage delete returned False: {event_id}")
                    except Exception as kv_error:
                        logger.warning(
                            f"⚠️  KV-Storage delete failed for {event_id}: {kv_error}",
                            exc_info=True
                        )

                return True
            return False
        except Exception as e:
            logger.error("❌ Failed to soft delete MemCell by event_id: %s", e)
            return False

    async def hard_delete_by_event_id(
        self, event_id: str, session: Optional[AsyncClientSession] = None
    ) -> bool:
        """
        Hard delete (physical deletion) MemCell by event_id

        ⚠️ Warning: This operation is irreversible! Use with caution.

        Args:
            event_id: Event ID
            session: Optional MongoDB session

        Returns:
            True if deleted, False otherwise
        """
        try:
            memcell = await self.model.hard_find_one({"_id": ObjectId(event_id)})
            if memcell:
                # 1. Delete from MongoDB (primary operation)
                await memcell.hard_delete(session=session)
                logger.debug(
                    "✅ Successfully hard deleted MemCell by event_id: %s", event_id
                )

                # 2. Delete from KV-Storage
                kv_storage = self._get_kv_storage()
                if kv_storage:
                    try:
                        await kv_storage.delete(key=event_id)
                        logger.debug(f"✅ KV-Storage delete success: {event_id}")
                    except Exception as kv_error:
                        logger.warning(f"⚠️  KV-Storage delete failed: {kv_error}")

                return True
            return False
        except Exception as e:
            logger.error("❌ Failed to hard delete MemCell by event_id: %s", e)
            return False

    async def find_by_user_id(
        self,
        user_id: str,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
        sort_desc: bool = True,
    ) -> List[MemCell]:
        """
        Query MemCell by user ID

        Args:
            user_id: User ID
            limit: Maximum number of results
            skip: Number of results to skip
            sort_desc: Sort by timestamp descending (default True)

        Returns:
            List of full MemCell instances
        """
        try:
            # Use appropriate model based on storage mode
            mongo_model = self._get_mongo_model()

            # Build query
            query = mongo_model.find({"user_id": user_id})

            # Apply sorting
            sort_order = "-timestamp" if sort_desc else "timestamp"
            query = query.sort(sort_order)

            # Apply pagination
            if skip is not None:
                query = query.skip(skip)
            if limit is not None:
                query = query.limit(limit)

            # Execute query
            results = await query.to_list()
            logger.debug(f"✅ Found {len(results)} MemCell for user: {user_id}")

            # Process results based on storage mode
            full_memcells = await self._process_query_results(results)
            return full_memcells
        except Exception as e:
            logger.error("❌ Failed to query MemCell by user ID: %s", e)
            return []

    async def find_by_user_and_time_range(
        self,
        user_id: str,
        start_time: datetime,
        end_time: datetime,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
        sort_desc: bool = True,
    ) -> List[MemCell]:
        """
        Query MemCell by user ID and time range

        Args:
            user_id: User ID
            start_time: Start time (inclusive)
            end_time: End time (exclusive)
            limit: Maximum number of results
            skip: Number of results to skip
            sort_desc: Sort by timestamp descending (default True)

        Returns:
            List of full MemCell instances
        """
        try:
            # Use appropriate model based on storage mode
            mongo_model = self._get_mongo_model()

            # Build query with time range
            query_filter = And(
                Eq(mongo_model.user_id, user_id),
                GTE(mongo_model.timestamp, start_time),
                LT(mongo_model.timestamp, end_time),
            )
            query = mongo_model.find(query_filter)

            # Apply sorting
            sort_order = "-timestamp" if sort_desc else "timestamp"
            query = query.sort(sort_order)

            # Apply pagination
            if skip is not None:
                query = query.skip(skip)
            if limit is not None:
                query = query.limit(limit)

            # Execute query
            results = await query.to_list()
            logger.debug(
                f"✅ Found {len(results)} MemCell for user {user_id} in time range"
            )

            # Process results based on storage mode
            full_memcells = await self._process_query_results(results)
            return full_memcells
        except Exception as e:
            logger.error("❌ Failed to query MemCell by user and time range: %s", e)
            return []

    async def find_by_group_id(
        self,
        group_id: str,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
        sort_desc: bool = True,
    ) -> List[MemCell]:
        """
        Query MemCell by group ID

        Args:
            group_id: Group ID
            limit: Maximum number of results
            skip: Number of results to skip
            sort_desc: Sort by timestamp descending (default True)

        Returns:
            List of full MemCell instances
        """
        try:
            # Use appropriate model based on storage mode
            mongo_model = self._get_mongo_model()

            # Build query
            query = mongo_model.find({"group_id": group_id})

            # Apply sorting
            sort_order = "-timestamp" if sort_desc else "timestamp"
            query = query.sort(sort_order)

            # Apply pagination
            if skip is not None:
                query = query.skip(skip)
            if limit is not None:
                query = query.limit(limit)

            # Execute query
            results = await query.to_list()
            logger.debug(f"✅ Found {len(results)} MemCell for group: {group_id}")

            # Process results based on storage mode
            full_memcells = await self._process_query_results(results)
            return full_memcells
        except Exception as e:
            logger.error("❌ Failed to query MemCell by group ID: %s", e)
            return []

    async def find_by_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
        sort_desc: bool = True,
    ) -> List[MemCell]:
        """
        Query MemCell by time range

        Args:
            start_time: Start time (inclusive)
            end_time: End time (exclusive)
            limit: Maximum number of results
            skip: Number of results to skip
            sort_desc: Sort by timestamp descending (default True)

        Returns:
            List of full MemCell instances
        """
        try:
            # Use appropriate model based on storage mode
            mongo_model = self._get_mongo_model()

            # Build query with time range
            query_filter = And(
                GTE(mongo_model.timestamp, start_time),
                LT(mongo_model.timestamp, end_time),
            )
            query = mongo_model.find(query_filter)

            # Apply sorting
            sort_order = "-timestamp" if sort_desc else "timestamp"
            query = query.sort(sort_order)

            # Apply pagination
            if skip is not None:
                query = query.skip(skip)
            if limit is not None:
                query = query.limit(limit)

            # Execute query
            results = await query.to_list()
            logger.debug(f"✅ Found {len(results)} MemCell in time range")

            # Process results based on storage mode
            full_memcells = await self._process_query_results(results)
            return full_memcells
        except Exception as e:
            logger.error("❌ Failed to query MemCell by time range: %s", e)
            return []

    async def find_by_participants(
        self,
        participants: List[str],
        match_all: bool = False,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
    ) -> List[MemCell]:
        """
        Query MemCell by participants

        Args:
            participants: List of participant names
            match_all: If True, match all participants; if False, match any
            limit: Maximum number of results
            skip: Number of results to skip

        Returns:
            List of full MemCell instances
        """
        try:
            # Use appropriate model based on storage mode
            mongo_model = self._get_mongo_model()

            # Build query based on match mode
            if match_all:
                # Match all participants
                query = mongo_model.find({"participants": {"$all": participants}})
            else:
                # Match any participant
                query = mongo_model.find({"participants": {"$in": participants}})

            # Apply sorting
            query = query.sort("-timestamp")

            # Apply pagination
            if skip is not None:
                query = query.skip(skip)
            if limit is not None:
                query = query.limit(limit)

            # Execute query
            results = await query.to_list()
            logger.debug(f"✅ Found {len(results)} MemCell for participants")

            # Process results based on storage mode
            full_memcells = await self._process_query_results(results)
            return full_memcells
        except Exception as e:
            logger.error("❌ Failed to query MemCell by participants: %s", e)
            return []

    async def search_by_keywords(
        self,
        keywords: List[str],
        match_all: bool = False,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
    ) -> List[MemCell]:
        """
        Search MemCell by keywords

        Args:
            keywords: List of keywords
            match_all: If True, match all keywords; if False, match any
            limit: Maximum number of results
            skip: Number of results to skip

        Returns:
            List of full MemCell instances
        """
        try:
            # Use appropriate model based on storage mode
            mongo_model = self._get_mongo_model()

            # Build query based on match mode
            if match_all:
                # Match all keywords
                query = mongo_model.find({"keywords": {"$all": keywords}})
            else:
                # Match any keyword
                query = mongo_model.find({"keywords": {"$in": keywords}})

            # Apply sorting
            query = query.sort("-timestamp")

            # Apply pagination
            if skip is not None:
                query = query.skip(skip)
            if limit is not None:
                query = query.limit(limit)

            # Execute query
            results = await query.to_list()
            logger.debug(f"✅ Found {len(results)} MemCell matching keywords")

            # Process results based on storage mode
            full_memcells = await self._process_query_results(results)
            return full_memcells
        except Exception as e:
            logger.error("❌ Failed to search MemCell by keywords: %s", e)
            return []

    async def delete_by_user_id(
        self,
        user_id: str,
        deleted_by: Optional[str] = None,
        session: Optional[AsyncClientSession] = None,
    ) -> int:
        """
        Soft delete all MemCell of a user

        Args:
            user_id: User ID
            deleted_by: Deleter (optional)
            session: Optional MongoDB session, for transaction support

        Returns:
            Number of soft deleted records
        """
        try:
            result = await self.model.delete_many(
                {"user_id": user_id}, deleted_by=deleted_by, session=session
            )
            count = result.modified_count if result else 0
            logger.info(
                "✅ Successfully soft deleted all MemCell of user: %s, deleted %d records",
                user_id,
                count,
            )
            return count
        except Exception as e:
            logger.error("❌ Failed to soft delete all MemCell of user: %s", e)
            return 0

    async def hard_delete_by_user_id(
        self, user_id: str, session: Optional[AsyncClientSession] = None
    ) -> int:
        """
        Hard delete (physical deletion) all MemCell of a user

        ⚠️ Warning: This operation is irreversible! Use with caution.

        Args:
            user_id: User ID
            session: Optional MongoDB session

        Returns:
            Number of hard deleted records
        """
        try:
            # 1. Query all event_ids to be deleted (for KV-Storage batch delete)
            event_ids = []
            kv_storage = self._get_kv_storage()
            if kv_storage:
                try:
                    memcells = await self.model.find({"user_id": user_id}).to_list()
                    event_ids = [str(mc.id) for mc in memcells]
                    logger.debug(f"Found {len(event_ids)} MemCells to delete for user: {user_id}")
                except Exception as query_error:
                    logger.warning(f"Failed to query event_ids for KV batch delete: {query_error}")

            # 2. Delete from MongoDB (primary operation)
            result = await self.model.hard_delete_many(
                {"user_id": user_id}, session=session
            )
            count = result.deleted_count if result else 0
            logger.info(
                "✅ Successfully hard deleted all MemCell of user: %s, deleted %d records",
                user_id,
                count,
            )

            # 3. Batch delete from KV-Storage
            if event_ids:
                kv_storage = self._get_kv_storage()
                if kv_storage:
                    try:
                        deleted_count = await kv_storage.batch_delete(keys=event_ids)
                        logger.info(f"✅ KV-Storage batch delete: {deleted_count} records")
                    except Exception as kv_error:
                        logger.warning(f"⚠️  KV-Storage batch delete failed: {kv_error}")

            return count
        except Exception as e:
            logger.error("❌ Failed to hard delete all MemCell of user: %s", e)
            return 0

    async def delete_by_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
        user_id: Optional[str] = None,
        deleted_by: Optional[str] = None,
        session: Optional[AsyncClientSession] = None,
    ) -> int:
        """
        Soft delete MemCell within time range

        Args:
            start_time: Start time
            end_time: End time
            user_id: Optional user ID filter
            deleted_by: Deleter (optional)
            session: Optional MongoDB session, for transaction support

        Returns:
            Number of soft deleted records
        """
        try:
            filter_dict = {"timestamp": {"$gte": start_time, "$lt": end_time}}
            if user_id:
                filter_dict["user_id"] = user_id

            result = await self.model.delete_many(
                filter_dict, deleted_by=deleted_by, session=session
            )
            count = result.modified_count if result else 0
            logger.info(
                "✅ Successfully soft deleted MemCell within time range: %s - %s, user: %s, deleted %d records",
                start_time,
                end_time,
                user_id or 'all',
                count,
            )
            return count
        except Exception as e:
            logger.error("❌ Failed to soft delete MemCell within time range: %s", e)
            return 0

    async def hard_delete_by_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
        user_id: Optional[str] = None,
        session: Optional[AsyncClientSession] = None,
    ) -> int:
        """
        Hard delete (physical deletion) MemCell within time range

        ⚠️ Warning: This operation is irreversible! Use with caution.

        Args:
            start_time: Start time
            end_time: End time
            user_id: Optional user ID filter
            session: Optional MongoDB session, for transaction support

        Returns:
            Number of hard deleted records
        """
        try:
            filter_dict = {"timestamp": {"$gte": start_time, "$lt": end_time}}
            if user_id:
                filter_dict["user_id"] = user_id

            # 1. Query all event_ids to be deleted (for KV-Storage batch delete)
            event_ids = []
            kv_storage = self._get_kv_storage()
            if kv_storage:
                try:
                    memcells = await self.model.find(And(*conditions)).to_list()
                    event_ids = [str(mc.id) for mc in memcells]
                    logger.debug(f"Found {len(event_ids)} MemCells to delete in time range")
                except Exception as query_error:
                    logger.warning(f"Failed to query event_ids for KV batch delete: {query_error}")

            # 2. Delete from MongoDB (primary operation)
            result = await self.model.hard_delete_many(filter_dict, session=session)
            count = result.deleted_count if result else 0
            logger.info(
                "✅ Successfully hard deleted MemCell within time range: %s - %s, user: %s, deleted %d records",
                start_time,
                end_time,
                user_id or 'all',
                count,
            )
            return count
        except Exception as e:
            logger.error("❌ Failed to hard delete MemCell within time range: %s", e)
            return 0

    # ==================== Soft Delete Recovery Methods ====================

    async def restore_by_event_id(
        self, event_id: str, session: Optional[AsyncClientSession] = None
    ) -> bool:
        """
        Restore soft-deleted MemCell by event_id

        Args:
            event_id: Event ID

        Returns:
            Returns True if restoration succeeds, otherwise False
        """
        try:
            memcell = await self.model.hard_find_one(
                {"_id": ObjectId(event_id)}, session=session
            )
            if memcell:
                await memcell.restore()
                logger.debug(
                    "✅ Successfully restored MemCell by event_id: %s", event_id
                )
                return True
            return False
        except Exception as e:
            logger.error("❌ Failed to restore MemCell by event_id: %s", e)
            return False

    async def restore_by_user_id(
        self, user_id: str, session: Optional[AsyncClientSession] = None
    ) -> int:
        """
        Restore all soft-deleted MemCell of a user

        Args:
            user_id: User ID
            session: Optional MongoDB session, for transaction support

        Returns:
            Number of restored records
        """
        try:
            result = await self.model.restore_many(
                {"user_id": user_id}, session=session
            )
            count = result.modified_count if result else 0
            logger.info(
                "✅ Successfully restored all MemCell of user: %s, restored %d records",
                user_id,
                count,
            )
            return count
        except Exception as e:
            logger.error("❌ Failed to restore all MemCell of user: %s", e)
            return 0

    async def restore_by_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
        user_id: Optional[str] = None,
        session: Optional[AsyncClientSession] = None,
    ) -> int:
        """
        Restore soft-deleted MemCell within time range

        Args:
            start_time: Start time
            end_time: End time
            user_id: Optional user ID filter
            session: Optional MongoDB session, for transaction support

        Returns:
            Number of restored records
        """
        try:
            filter_dict = {
                "timestamp": {"$gte": start_time, "$lt": end_time},
                "deleted_at": {"$ne": None},  # Only restore deleted records
            }
            if user_id:
                filter_dict["user_id"] = user_id

            result = await self.model.restore_many(filter_dict, session=session)
            count = result.modified_count if result else 0
            logger.info(
                "✅ Successfully restored MemCell within time range: %s - %s, user: %s, restored %d records",
                start_time,
                end_time,
                user_id or 'all',
                count,
            )
            return count
        except Exception as e:
            logger.error("❌ Failed to restore MemCell within time range: %s", e)
            return 0

    async def count_by_user_id(self, user_id: str) -> int:
        """
        Count MemCell by user ID

        Args:
            user_id: User ID

        Returns:
            Total count
        """
        try:
            # Use appropriate model based on storage mode
            mongo_model = self._get_mongo_model()
            count = await mongo_model.find({"user_id": user_id}).count()
            logger.debug(f"✅ Count for user {user_id}: {count}")
            return count
        except Exception as e:
            logger.error("❌ Failed to count MemCell by user ID: %s", e)
            return 0

    async def count_by_time_range(
        self, start_time: datetime, end_time: datetime
    ) -> int:
        """
        Count MemCell by time range

        Args:
            start_time: Start time (inclusive)
            end_time: End time (exclusive)

        Returns:
            Total count
        """
        try:
            # Use appropriate model based on storage mode
            mongo_model = self._get_mongo_model()
            query_filter = And(
                GTE(mongo_model.timestamp, start_time),
                LT(mongo_model.timestamp, end_time),
            )
            count = await mongo_model.find(query_filter).count()
            logger.debug(f"✅ Count in time range: {count}")
            return count
        except Exception as e:
            logger.error("❌ Failed to count MemCell by time range: %s", e)
            return 0

    async def get_latest_by_user(
        self, user_id: str, limit: int = 10
    ) -> List[MemCell]:
        """
        Get latest MemCell for a user

        Args:
            user_id: User ID
            limit: Maximum number of results (default 10)

        Returns:
            List of full MemCell instances sorted by timestamp descending
        """
        try:
            # Use appropriate model based on storage mode
            mongo_model = self._get_mongo_model()

            # Query with limit and sort
            results = await (
                mongo_model.find({"user_id": user_id})
                .sort("-timestamp")
                .limit(limit)
                .to_list()
            )
            logger.debug(f"✅ Found {len(results)} latest MemCell for user: {user_id}")

            # Process results based on storage mode
            full_memcells = await self._process_query_results(results)
            return full_memcells
        except Exception as e:
            logger.error("❌ Failed to get latest MemCell by user: %s", e)
            return []


# Export
__all__ = ["MemCellRawRepository"]
