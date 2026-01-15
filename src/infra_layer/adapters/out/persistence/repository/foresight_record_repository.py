"""
ForesightRecord Repository

Provides generic CRUD operations and query capabilities for foresight records.
"""

from typing import List, Optional, Type, TypeVar, Union
from pymongo.asynchronous.client_session import AsyncClientSession
from bson import ObjectId
from core.observation.logger import get_logger
from core.di.decorators import repository
from core.di import get_bean_by_type
from core.oxm.mongo.base_repository import BaseRepository
from infra_layer.adapters.out.persistence.document.memory.foresight_record import (
    ForesightRecord,
    ForesightRecordProjection,
)
from infra_layer.adapters.out.persistence.document.memory.foresight_record_lite import (
    ForesightRecordLite,
)
from infra_layer.adapters.out.persistence.kv_storage.kv_storage_interface import (
    KVStorageInterface,
)

# Define generic type variable
T = TypeVar('T', ForesightRecord, ForesightRecordProjection)

logger = get_logger(__name__)


@repository("foresight_record_repository", primary=True)
class ForesightRecordRawRepository(BaseRepository[ForesightRecordLite]):
    """
    Raw repository for personal foresight data

    Provides CRUD operations and basic query functions for personal foresight records.
    Note: Vectors should be generated during extraction; this Repository is not responsible for vector generation.

    Uses Dual Storage architecture:
    - MongoDB: Stores ForesightRecordLite (indexed fields only)
    - KV-Storage: Stores complete ForesightRecord (full data)
    """

    def __init__(self):
        super().__init__(ForesightRecordLite)

        # Inject KV-Storage with graceful degradation
        self._kv_storage: Optional[KVStorageInterface] = None
        try:
            self._kv_storage = get_bean_by_type(KVStorageInterface)
            logger.info("✅ ForesightRecord KV-Storage initialized successfully")
        except Exception as e:
            logger.error(f"⚠️ ForesightRecord KV-Storage not available: {e}")
            raise e

    def _get_kv_storage(self) -> Optional[KVStorageInterface]:
        """
        Get KV-Storage instance with availability check.

        Returns:
            KV-Storage instance if available

        Raises:
            Exception: If KV-Storage is not available
        """
        if self._kv_storage is None:
            logger.debug("KV-Storage not available, skipping KV operations")
            raise Exception("KV-Storage not available")
        return self._kv_storage

    def _foresight_to_lite(self, foresight: ForesightRecord) -> ForesightRecordLite:
        """
        Convert full ForesightRecord to ForesightRecordLite (only indexed fields).

        Args:
            foresight: Full ForesightRecord object

        Returns:
            ForesightRecordLite with only indexed fields

        Note:
            Audit fields (created_at/updated_at) are not copied here.
            They will be automatically set by AuditBase during insert/update operations.
        """
        return ForesightRecordLite(
            id=foresight.id,
            user_id=foresight.user_id,
            group_id=foresight.group_id,
            parent_episode_id=foresight.parent_episode_id,
        )

    async def _foresight_lite_to_full(
        self, results: List[ForesightRecordLite]
    ) -> List[ForesightRecord]:
        """
        Reconstruct full ForesightRecord objects from KV-Storage.
        MongoDB is ONLY used for querying and getting _id list.

        Args:
            results: List of ForesightRecordLite from MongoDB query

        Returns:
            List of full ForesightRecord objects from KV-Storage
        """
        if not results:
            return []

        kv_storage = self._get_kv_storage()
        if not kv_storage:
            logger.error("❌ KV-Storage unavailable, cannot reconstruct ForesightRecords")
            return []

        # Extract event IDs from MongoDB results
        kv_keys = [str(r.id) for r in results]

        # Batch get from KV-Storage (source of truth)
        kv_data_dict = await kv_storage.batch_get(keys=kv_keys)

        # Reconstruct full ForesightRecords
        full_foresights = []
        for result in results:
            memory_id = str(result.id)
            kv_json = kv_data_dict.get(memory_id)
            if kv_json:
                try:
                    full_foresight = ForesightRecord.model_validate_json(kv_json)
                    full_foresights.append(full_foresight)
                except Exception as e:
                    logger.error(
                        f"❌ Failed to deserialize ForesightRecord: {memory_id}, error: {e}"
                    )
            else:
                logger.warning(f"⚠️ ForesightRecord not found in KV-Storage: {memory_id}")

        logger.debug(
            f"✅ Reconstructed {len(full_foresights)}/{len(results)} ForesightRecords"
        )
        return full_foresights

    def _convert_to_projection_if_needed(
        self,
        full_foresights: List[ForesightRecord],
        target_model: Optional[Type[T]] = None,
    ) -> List[Union[ForesightRecord, ForesightRecordProjection]]:
        """
        Convert full ForesightRecord objects to Projection if needed.

        Args:
            full_foresights: List of full ForesightRecord objects
            target_model: Target model type

        Returns:
            List of converted objects
        """
        if not target_model or target_model == ForesightRecord:
            return full_foresights

        if target_model == ForesightRecordProjection:
            return [
                ForesightRecordProjection(
                    id=f.id,
                    user_id=f.user_id,
                    user_name=f.user_name,
                    group_id=f.group_id,
                    group_name=f.group_name,
                    content=f.content,
                    parent_episode_id=f.parent_episode_id,
                    start_time=f.start_time,
                    end_time=f.end_time,
                    duration_days=f.duration_days,
                    participants=f.participants,
                    vector_model=f.vector_model,
                    evidence=f.evidence,
                    extend=f.extend,
                    created_at=f.created_at,
                    updated_at=f.updated_at,
                )
                for f in full_foresights
            ]

        return full_foresights

    # ==================== Basic CRUD Methods ====================

    async def save(
        self, foresight: ForesightRecord, session: Optional[AsyncClientSession] = None
    ) -> Optional[ForesightRecord]:
        """
        Save personal foresight record

        Args:
            foresight: ForesightRecord object
            session: Optional MongoDB session for transaction support

        Returns:
            Saved ForesightRecord or None
        """
        try:
            # 1. Write ForesightRecordLite to MongoDB (indexed fields only)
            # Note: ForesightRecordLite inherits AuditBase, which will auto-set created_at/updated_at on insert
            foresight_lite = self._foresight_to_lite(foresight)
            await foresight_lite.insert(session=session)

            # Copy generated ID and audit fields back to full ForesightRecord
            # (AuditBase has set these fields automatically during insert)
            foresight.id = foresight_lite.id
            foresight.created_at = foresight_lite.created_at
            foresight.updated_at = foresight_lite.updated_at

            logger.info(
                "✅ Saved personal foresight successfully: id=%s, user_id=%s, parent_episode=%s",
                foresight.id,
                foresight.user_id,
                foresight.parent_episode_id,
            )

            # 2. Write to KV-Storage (always full ForesightRecord)
            kv_storage = self._get_kv_storage()
            if kv_storage:
                try:
                    json_value = foresight.model_dump_json(
                        by_alias=True, exclude_none=False
                    )
                    success = await kv_storage.put(
                        key=str(foresight.id), value=json_value
                    )
                    if success:
                        logger.debug(f"✅ KV-Storage write success: {foresight.id}")
                    else:
                        logger.error(f"⚠️  KV-Storage write failed: {foresight.id}")
                        return None
                except Exception as kv_error:
                    logger.error(
                        f"⚠️  KV-Storage write error: {foresight.id}: {kv_error}"
                    )
                    return None

            return foresight
        except Exception as e:
            logger.error("❌ Failed to save personal foresight: %s", e)
            return None

    async def get_by_id(
        self,
        memory_id: str,
        session: Optional[AsyncClientSession] = None,
        model: Optional[Type[T]] = None,
    ) -> Optional[Union[ForesightRecord, ForesightRecordProjection]]:
        """
        Retrieve personal foresight by ID

        Args:
            memory_id: Memory ID
            session: Optional MongoDB session for transaction support
            model: Type of model to return, defaults to ForesightRecord (full version)

        Returns:
            Foresight object of specified type or None
        """
        try:
            object_id = ObjectId(memory_id)

            # Query MongoDB Lite model first
            lite_result = await self.model.find_one({"_id": object_id}, session=session)
            if not lite_result:
                logger.debug("ℹ️  Personal foresight not found: id=%s", memory_id)
                return None

            # Reconstruct from KV-Storage
            full_foresights = await self._foresight_lite_to_full([lite_result])
            if not full_foresights:
                return None

            # Convert to target model type if needed
            results = self._convert_to_projection_if_needed(full_foresights, model)
            result = results[0] if results else None

            if result:
                target_model = model if model is not None else ForesightRecord
                logger.debug(
                    "✅ Retrieved personal foresight by ID successfully: %s (model=%s)",
                    memory_id,
                    target_model.__name__,
                )
            return result
        except Exception as e:
            logger.error("❌ Failed to retrieve personal foresight by ID: %s", e)
            return None

    async def get_by_parent_episode_id(
        self,
        parent_episode_id: str,
        session: Optional[AsyncClientSession] = None,
        model: Optional[Type[T]] = None,
    ) -> List[Union[ForesightRecord, ForesightRecordProjection]]:
        """
        Retrieve all foresights by parent episodic memory ID

        Args:
            parent_episode_id: Parent episodic memory ID
            session: Optional MongoDB session for transaction support
            model: Type of model to return, defaults to ForesightRecord (full version)

        Returns:
            List of foresight objects of specified type
        """
        try:
            # Query MongoDB Lite model
            query = self.model.find(
                {"parent_episode_id": parent_episode_id}, session=session
            )
            lite_results = await query.to_list()

            # Reconstruct from KV-Storage
            full_foresights = await self._foresight_lite_to_full(lite_results)

            # Convert to target model type if needed
            results = self._convert_to_projection_if_needed(full_foresights, model)

            target_model = model if model is not None else ForesightRecord
            logger.debug(
                "✅ Retrieved foresights by parent episodic memory ID successfully: %s, found %d records (model=%s)",
                parent_episode_id,
                len(results),
                target_model.__name__,
            )
            return results
        except Exception as e:
            logger.error(
                "❌ Failed to retrieve foresights by parent episodic memory ID: %s", e
            )
            return []

    async def get_by_user_id(
        self,
        user_id: str,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
        session: Optional[AsyncClientSession] = None,
        model: Optional[Type[T]] = None,
    ) -> List[Union[ForesightRecord, ForesightRecordProjection]]:
        """
        Retrieve list of foresights by user ID

        Args:
            user_id: User ID
            limit: Limit number of returned records
            skip: Number of records to skip
            session: Optional MongoDB session for transaction support
            model: Type of model to return, defaults to ForesightRecord (full version)

        Returns:
            List of foresight objects of specified type
        """
        try:
            # Query MongoDB Lite model
            query = self.model.find({"user_id": user_id}, session=session)

            if skip:
                query = query.skip(skip)
            if limit:
                query = query.limit(limit)

            lite_results = await query.to_list()

            # Reconstruct from KV-Storage
            full_foresights = await self._foresight_lite_to_full(lite_results)

            # Convert to target model type if needed
            results = self._convert_to_projection_if_needed(full_foresights, model)

            target_model = model if model is not None else ForesightRecord
            logger.debug(
                "✅ Retrieved foresights by user ID successfully: %s, found %d records (model=%s)",
                user_id,
                len(results),
                target_model.__name__,
            )
            return results
        except Exception as e:
            logger.error("❌ Failed to retrieve foresights by user ID: %s", e)
            return []

    async def delete_by_id(
        self, memory_id: str, session: Optional[AsyncClientSession] = None
    ) -> bool:
        """
        Delete personal foresight by ID

        Args:
            memory_id: Memory ID
            session: Optional MongoDB session for transaction support

        Returns:
            Whether deletion was successful
        """
        try:
            object_id = ObjectId(memory_id)

            # Delete from MongoDB
            result = await self.model.find({"_id": object_id}, session=session).delete()
            success = result.deleted_count > 0 if result else False

            if success:
                # Delete from KV-Storage
                kv_storage = self._get_kv_storage()
                if kv_storage:
                    try:
                        await kv_storage.delete(memory_id)
                    except Exception as kv_error:
                        logger.error(
                            f"⚠️  KV-Storage delete error: {memory_id}: {kv_error}"
                        )

                logger.info("✅ Deleted personal foresight successfully: %s", memory_id)
            else:
                logger.warning(
                    "⚠️  Personal foresight to delete not found: %s", memory_id
                )

            return success
        except Exception as e:
            logger.error("❌ Failed to delete personal foresight: %s", e)
            return False

    async def delete_by_parent_episode_id(
        self, parent_episode_id: str, session: Optional[AsyncClientSession] = None
    ) -> int:
        """
        Delete all foresights by parent episodic memory ID

        Args:
            parent_episode_id: Parent episodic memory ID
            session: Optional MongoDB session for transaction support

        Returns:
            Number of deleted records
        """
        try:
            # Get all IDs first for KV-Storage deletion
            lite_results = await self.model.find(
                {"parent_episode_id": parent_episode_id}, session=session
            ).to_list()
            memory_ids = [str(result.id) for result in lite_results]

            # Delete from MongoDB
            result = await self.model.find(
                {"parent_episode_id": parent_episode_id}, session=session
            ).delete()
            count = result.deleted_count if result else 0

            # Delete from KV-Storage
            if count > 0 and memory_ids:
                kv_storage = self._get_kv_storage()
                if kv_storage:
                    try:
                        await kv_storage.batch_delete(memory_ids)
                    except Exception as kv_error:
                        logger.error(
                            f"⚠️  KV-Storage batch delete error for parent {parent_episode_id}: {kv_error}"
                        )

            logger.info(
                "✅ Deleted foresights by parent episodic memory ID successfully: %s, deleted %d records",
                parent_episode_id,
                count,
            )
            return count
        except Exception as e:
            logger.error(
                "❌ Failed to delete foresights by parent episodic memory ID: %s", e
            )
            return 0


# Export
__all__ = ["ForesightRecordRawRepository"]
