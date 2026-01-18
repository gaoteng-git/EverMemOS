"""
EventLogRecord Repository

Provides CRUD operations and query capabilities for generic event logs.
"""

from datetime import datetime
from typing import List, Optional, Type, TypeVar, Union
from pymongo.asynchronous.client_session import AsyncClientSession
from bson import ObjectId
from core.observation.logger import get_logger
from core.di.decorators import repository
from core.oxm.mongo.base_repository import BaseRepository
from common_utils.datetime_utils import get_now_with_timezone
from infra_layer.adapters.out.persistence.document.memory.event_log_record import (
    EventLogRecord,
    EventLogRecordProjection,
)
from infra_layer.adapters.out.persistence.document.memory.event_log_record_lite import (
    EventLogRecordLite,
)
from infra_layer.adapters.out.persistence.repository.dual_storage_helper import (
    DualStorageHelper,
)

# Define generic type variable
T = TypeVar('T', EventLogRecord, EventLogRecordProjection)

logger = get_logger(__name__)


@repository("event_log_record_repository", primary=True)
class EventLogRecordRawRepository(BaseRepository[EventLogRecordLite]):
    """
    Personal event log raw data repository

    Provides CRUD operations and basic query functions for personal event logs.
    Note: Vectors should be generated during extraction; this Repository is not responsible for vector generation.
    """

    def __init__(self):
        super().__init__(EventLogRecordLite)
        self._dual_storage = DualStorageHelper[EventLogRecord, EventLogRecordLite](
            model_name="EventLogRecord", full_model=EventLogRecord
        )

    def _event_log_to_lite(self, event_log: EventLogRecord) -> EventLogRecordLite:
        """
        Convert full EventLogRecord to EventLogRecordLite (only indexed fields).

        Args:
            event_log: Full EventLogRecord object

        Returns:
            EventLogRecordLite with only indexed fields

        Note:
            Audit fields (created_at/updated_at) are not copied here.
            They will be automatically set by AuditBase during insert/update operations.
        """
        return EventLogRecordLite(
            id=event_log.id,
            user_id=event_log.user_id,
            group_id=event_log.group_id,
            parent_episode_id=event_log.parent_episode_id,
            timestamp=event_log.timestamp,
        )

    async def _event_log_lite_to_full(
        self, results: List[EventLogRecordLite]
    ) -> List[EventLogRecord]:
        """
        Reconstruct full EventLogRecord objects from KV-Storage.

        Args:
            results: List of EventLogRecordLite from MongoDB query

        Returns:
            List of complete EventLogRecord objects
        """
        return await self._dual_storage.reconstruct_batch(results)

    def _convert_to_projection_if_needed(
        self,
        full_event_logs: List[EventLogRecord],
        target_model: Optional[Type[T]] = None,
    ) -> List[Union[EventLogRecord, EventLogRecordProjection]]:
        """
        Convert full EventLogRecord objects to Projection if needed.

        Args:
            full_event_logs: List of full EventLogRecord objects
            target_model: Target model type

        Returns:
            List of converted objects
        """
        if not target_model or target_model == EventLogRecord:
            return full_event_logs

        if target_model == EventLogRecordProjection:
            return [
                EventLogRecordProjection(
                    id=log.id,
                    user_id=log.user_id,
                    user_name=log.user_name,
                    group_id=log.group_id,
                    group_name=log.group_name,
                    atomic_fact=log.atomic_fact,
                    parent_episode_id=log.parent_episode_id,
                    timestamp=log.timestamp,
                    participants=log.participants,
                    vector_model=log.vector_model,
                    event_type=log.event_type,
                    extend=log.extend,
                    created_at=log.created_at,
                    updated_at=log.updated_at,
                )
                for log in full_event_logs
            ]

        return full_event_logs

    # ==================== Basic CRUD Methods ====================

    async def save(
        self, event_log: EventLogRecord, session: Optional[AsyncClientSession] = None
    ) -> Optional[EventLogRecord]:
        """
        Save personal event log

        Args:
            event_log: Personal event log object
            session: Optional MongoDB session, for transaction support

        Returns:
            Saved EventLogRecord or None
        """
        try:
            # 1. Write EventLogRecordLite to MongoDB (indexed fields only)
            # Note: EventLogRecordLite inherits AuditBase, which will auto-set created_at/updated_at on insert
            event_log_lite = self._event_log_to_lite(event_log)
            await event_log_lite.insert(session=session)

            # Copy generated ID and audit fields back to full EventLogRecord
            # (AuditBase has set these fields automatically during insert)
            event_log.id = event_log_lite.id
            event_log.created_at = event_log_lite.created_at
            event_log.updated_at = event_log_lite.updated_at

            logger.info(
                "✅ Saved personal event log successfully: id=%s, user_id=%s, parent_episode=%s",
                event_log.id,
                event_log.user_id,
                event_log.parent_episode_id,
            )

            # 2. Write to KV-Storage (always full EventLogRecord)
            success = await self._dual_storage.write_to_kv(event_log)
            return event_log if success else None
        except Exception as e:
            logger.error("❌ Failed to save personal event log: %s", e)
            return None

    async def get_by_id(
        self,
        log_id: str,
        session: Optional[AsyncClientSession] = None,
        model: Optional[Type[T]] = None,
    ) -> Optional[Union[EventLogRecord, EventLogRecordProjection]]:
        """
        Get personal event log by ID

        Args:
            log_id: Log ID
            session: Optional MongoDB session, for transaction support
            model: Returned model type, default is EventLogRecord (full version), can pass EventLogRecordProjection

        Returns:
            Event log object of specified type or None
        """
        try:
            object_id = ObjectId(log_id)

            # Query MongoDB Lite model first
            lite_result = await self.model.find_one({"_id": object_id}, session=session)
            if not lite_result:
                logger.debug("ℹ️  Personal event log not found: id=%s", log_id)
                return None

            # Reconstruct from KV-Storage
            full_event_logs = await self._event_log_lite_to_full([lite_result])
            if not full_event_logs:
                return None

            # Convert to target model type if needed
            results = self._convert_to_projection_if_needed(full_event_logs, model)
            result = results[0] if results else None

            if result:
                target_model = model if model is not None else EventLogRecord
                logger.debug(
                    "✅ Retrieved personal event log by ID successfully: %s (model=%s)",
                    log_id,
                    target_model.__name__,
                )
            return result
        except Exception as e:
            logger.error("❌ Failed to retrieve personal event log by ID: %s", e)
            return None

    async def get_by_parent_episode_id(
        self,
        parent_episode_id: str,
        session: Optional[AsyncClientSession] = None,
        model: Optional[Type[T]] = None,
    ) -> List[Union[EventLogRecord, EventLogRecordProjection]]:
        """
        Get all event logs by parent episodic memory ID

        Args:
            parent_episode_id: Parent episodic memory ID
            session: Optional MongoDB session, for transaction support
            model: Returned model type, default is EventLogRecord (full version), can pass EventLogRecordProjection

        Returns:
            List of event log objects of specified type
        """
        try:
            # Query MongoDB Lite model
            query = self.model.find(
                {"parent_episode_id": parent_episode_id}, session=session
            )
            lite_results = await query.to_list()

            # Reconstruct from KV-Storage
            full_event_logs = await self._event_log_lite_to_full(lite_results)

            # Convert to target model type if needed
            results = self._convert_to_projection_if_needed(full_event_logs, model)

            target_model = model if model is not None else EventLogRecord
            logger.debug(
                "✅ Retrieved event logs by parent episodic memory ID successfully: %s, found %d records (model=%s)",
                parent_episode_id,
                len(results),
                target_model.__name__,
            )
            return results
        except Exception as e:
            logger.error(
                "❌ Failed to retrieve event logs by parent episodic memory ID: %s", e
            )
            return []

    async def get_by_user_id(
        self,
        user_id: str,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
        sort_desc: bool = True,
        session: Optional[AsyncClientSession] = None,
        model: Optional[Type[T]] = None,
    ) -> List[Union[EventLogRecord, EventLogRecordProjection]]:
        """
        Get list of event logs by user ID

        Args:
            user_id: User ID
            limit: Limit number of returned records
            skip: Number of records to skip
            sort_desc: Whether to sort by time in descending order
            session: Optional MongoDB session, for transaction support
            model: Returned model type, default is EventLogRecord (full version), can pass EventLogRecordProjection

        Returns:
            List of event log objects of specified type
        """
        try:
            # Query MongoDB Lite model
            query = self.model.find({"user_id": user_id}, session=session)

            if sort_desc:
                query = query.sort("-timestamp")
            else:
                query = query.sort("timestamp")

            if skip:
                query = query.skip(skip)
            if limit:
                query = query.limit(limit)

            lite_results = await query.to_list()

            # Reconstruct from KV-Storage
            full_event_logs = await self._event_log_lite_to_full(lite_results)

            # Convert to target model type if needed
            results = self._convert_to_projection_if_needed(full_event_logs, model)

            target_model = model if model is not None else EventLogRecord
            logger.debug(
                "✅ Retrieved event logs by user ID successfully: %s, found %d records (model=%s)",
                user_id,
                len(results),
                target_model.__name__,
            )
            return results
        except Exception as e:
            logger.error("❌ Failed to retrieve event logs by user ID: %s", e)
            return []

    async def find_by_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
        user_id: Optional[str] = None,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
        sort_desc: bool = False,
        session: Optional[AsyncClientSession] = None,
        model: Optional[Type[T]] = None,
    ) -> List[Union[EventLogRecord, EventLogRecordProjection]]:
        """
        Query event logs by time range

        Args:
            start_time: Start time
            end_time: End time
            user_id: Optional user ID filter
            limit: Limit number of returned records
            skip: Number of records to skip
            sort_desc: Whether to sort by time in descending order, default False (ascending)
            session: Optional MongoDB session, for transaction support
            model: Returned model type, default is EventLogRecord (full version), can pass EventLogRecordProjection

        Returns:
            List of event log objects of specified type
        """
        try:
            filter_dict = {"timestamp": {"$gte": start_time, "$lt": end_time}}
            if user_id:
                filter_dict["user_id"] = user_id

            # Query MongoDB Lite model
            query = self.model.find(filter_dict, session=session)

            if sort_desc:
                query = query.sort("-timestamp")
            else:
                query = query.sort("timestamp")

            if skip:
                query = query.skip(skip)
            if limit:
                query = query.limit(limit)

            lite_results = await query.to_list()

            # Reconstruct from KV-Storage
            full_event_logs = await self._event_log_lite_to_full(lite_results)

            # Convert to target model type if needed
            results = self._convert_to_projection_if_needed(full_event_logs, model)

            target_model = model if model is not None else EventLogRecord
            logger.debug(
                "✅ Queried event logs by time range successfully: Time range: %s - %s, found %d records (model=%s)",
                start_time,
                end_time,
                len(results),
                target_model.__name__,
            )
            return results
        except Exception as e:
            logger.error("❌ Failed to query event logs by time range: %s", e)
            return []

    async def delete_by_id(
        self, log_id: str, session: Optional[AsyncClientSession] = None
    ) -> bool:
        """
        Delete personal event log by ID

        Args:
            log_id: Log ID
            session: Optional MongoDB session, for transaction support

        Returns:
            Whether deletion was successful
        """
        try:
            object_id = ObjectId(log_id)

            # Delete from MongoDB
            result = await self.model.find({"_id": object_id}, session=session).delete()
            success = result.deleted_count > 0 if result else False

            if success:
                # Delete from KV-Storage
                await self._dual_storage.delete_from_kv(log_id)
                logger.info("✅ Deleted personal event log successfully: %s", log_id)
            else:
                logger.warning("⚠️  Personal event log to delete not found: %s", log_id)

            return success
        except Exception as e:
            logger.error("❌ Failed to delete personal event log: %s", e)
            return False

    async def delete_by_parent_episode_id(
        self, parent_episode_id: str, session: Optional[AsyncClientSession] = None
    ) -> int:
        """
        Delete all event logs by parent episodic memory ID

        Args:
            parent_episode_id: Parent episodic memory ID
            session: Optional MongoDB session, for transaction support

        Returns:
            Number of deleted records
        """
        try:
            # Get all IDs first for KV-Storage deletion
            lite_results = await self.model.find(
                {"parent_episode_id": parent_episode_id}, session=session
            ).to_list()
            event_log_ids = [str(result.id) for result in lite_results]

            # Delete from MongoDB
            result = await self.model.find(
                {"parent_episode_id": parent_episode_id}, session=session
            ).delete()
            count = result.deleted_count if result else 0

            # Delete from KV-Storage
            if count > 0 and event_log_ids:
                kv_storage = self._dual_storage.get_kv_storage()
                try:
                    await kv_storage.batch_delete(event_log_ids)
                except Exception as kv_error:
                    logger.error(
                        f"⚠️  KV-Storage batch delete error for parent {parent_episode_id}: {kv_error}"
                    )

            logger.info(
                "✅ Deleted event logs by parent episodic memory ID successfully: %s, deleted %d records",
                parent_episode_id,
                count,
            )
            return count
        except Exception as e:
            logger.error(
                "❌ Failed to delete event logs by parent episodic memory ID: %s", e
            )
            return 0


# Export
__all__ = ["EventLogRecordRawRepository"]
