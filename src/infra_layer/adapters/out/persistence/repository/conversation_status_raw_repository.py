from typing import Optional, Dict, Any
from pymongo.asynchronous.client_session import AsyncClientSession
from core.oxm.mongo.base_repository import BaseRepository
from core.di import get_bean_by_type
from infra_layer.adapters.out.persistence.document.memory.conversation_status import (
    ConversationStatus,
)
from infra_layer.adapters.out.persistence.document.memory.conversation_status_lite import (
    ConversationStatusLite,
)
from infra_layer.adapters.out.persistence.kv_storage.kv_storage_interface import (
    KVStorageInterface,
)
from core.observation.logger import get_logger
from core.di.decorators import repository

logger = get_logger(__name__)


@repository("conversation_status_raw_repository", primary=True)
class ConversationStatusRawRepository(BaseRepository[ConversationStatusLite]):
    """
    Conversation status raw data repository

    Provides CRUD operations and query capabilities for conversation status data.
    """

    def __init__(self):
        super().__init__(ConversationStatusLite)

        # Inject KV-Storage with graceful degradation
        self._kv_storage: Optional[KVStorageInterface] = None
        try:
            self._kv_storage = get_bean_by_type(KVStorageInterface)
            logger.info("✅ ConversationStatus KV-Storage initialized successfully")
        except Exception as e:
            logger.error(f"⚠️ ConversationStatus KV-Storage not available: {e}")
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

    def _conversation_status_to_lite(
        self, conversation_status: ConversationStatus
    ) -> ConversationStatusLite:
        """
        Convert full ConversationStatus to ConversationStatusLite (only indexed fields).

        Args:
            conversation_status: Full ConversationStatus object

        Returns:
            ConversationStatusLite with only indexed fields

        Note:
            Audit fields (created_at/updated_at) are not copied here.
            They will be automatically set by AuditBase during insert/update operations.
        """
        return ConversationStatusLite(
            id=conversation_status.id,
            group_id=conversation_status.group_id,
        )

    async def _conversation_status_lite_to_full(
        self, lite: ConversationStatusLite
    ) -> Optional[ConversationStatus]:
        """
        Reconstruct full ConversationStatus object from KV-Storage.
        MongoDB is ONLY used for querying and getting _id.

        Args:
            lite: ConversationStatusLite from MongoDB query

        Returns:
            Full ConversationStatus object from KV-Storage or None
        """
        if not lite:
            return None

        kv_storage = self._get_kv_storage()
        if not kv_storage:
            logger.error("❌ KV-Storage unavailable, cannot reconstruct ConversationStatus")
            return None

        # Get from KV-Storage (source of truth)
        conversation_status_id = str(lite.id)
        kv_json = await kv_storage.get(conversation_status_id)

        if kv_json:
            try:
                full_conversation_status = ConversationStatus.model_validate_json(kv_json)
                return full_conversation_status
            except Exception as e:
                logger.error(
                    f"❌ Failed to deserialize ConversationStatus: {conversation_status_id}, error: {e}"
                )
                return None
        else:
            logger.warning(
                f"⚠️ ConversationStatus not found in KV-Storage: {conversation_status_id}"
            )
            return None

    # ==================== Basic CRUD Operations ====================

    async def get_by_group_id(
        self, group_id: str, session: Optional[AsyncClientSession] = None
    ) -> Optional[ConversationStatus]:
        """Get conversation status by group ID"""
        try:
            # Query MongoDB Lite model first
            lite_result = await self.model.find_one({"group_id": group_id}, session=session)
            if not lite_result:
                logger.debug("⚠️  Conversation status not found: group_id=%s", group_id)
                return None

            # Reconstruct from KV-Storage
            full_conversation_status = await self._conversation_status_lite_to_full(
                lite_result
            )
            if full_conversation_status:
                logger.debug(
                    "✅ Successfully retrieved conversation status by group ID: %s",
                    group_id,
                )
            return full_conversation_status
        except Exception as e:
            logger.error("❌ Failed to retrieve conversation status by group ID: %s", e)
            return None

    async def delete_by_group_id(
        self, group_id: str, session: Optional[AsyncClientSession] = None
    ) -> bool:
        """Delete conversation status by group ID"""
        try:
            # Get the lite object first to obtain ID for KV-Storage deletion
            lite = await self.model.find_one({"group_id": group_id}, session=session)
            if not lite:
                logger.warning(
                    "⚠️  Conversation status to delete not found: group_id=%s", group_id
                )
                return False

            conversation_status_id = str(lite.id)

            # Delete from MongoDB
            await lite.delete(session=session)

            # Delete from KV-Storage
            kv_storage = self._get_kv_storage()
            if kv_storage:
                try:
                    await kv_storage.delete(conversation_status_id)
                except Exception as kv_error:
                    logger.error(f"⚠️  KV-Storage delete error: {kv_error}")

            logger.info(
                "✅ Successfully deleted conversation status by group ID: %s", group_id
            )
            return True
        except Exception as e:
            logger.error("❌ Failed to delete conversation status by group ID: %s", e)
            return False

    async def upsert_by_group_id(
        self,
        group_id: str,
        update_data: Dict[str, Any],
        session: Optional[AsyncClientSession] = None,
    ) -> Optional[ConversationStatus]:
        """Update or insert conversation status by group ID

        Uses MongoDB atomic upsert operation to avoid concurrency race conditions.
        If a matching record is found, it updates it; otherwise, it creates a new record.
        Since group_id is unique, conversation_id will automatically use group_id as its value.

        Args:
            group_id: Group ID (will also be used as conversation_id)
            update_data: Data to update
            session: MongoDB session

        Returns:
            The updated or created conversation status record
        """
        try:
            # Check if already exists
            existing_lite = await self.model.find_one(
                {"group_id": group_id}, session=session
            )

            # Prepare full ConversationStatus object
            if existing_lite:
                # Update: reconstruct existing from KV-Storage
                existing = await self._conversation_status_lite_to_full(existing_lite)
                if not existing:
                    logger.error(
                        f"Failed to reconstruct existing conversation status from KV-Storage: group_id={group_id}"
                    )
                    return None

                # Update fields
                for key, value in update_data.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)

                # Update Lite in MongoDB (no indexed fields to update besides group_id)
                await existing_lite.save(session=session)

                # Copy updated audit fields back
                existing.created_at = existing_lite.created_at
                existing.updated_at = existing_lite.updated_at

                conversation_status = existing
                logger.debug(
                    f"Updated conversation status: group_id={group_id}"
                )
                print(
                    f"[ConversationStatusRawRepository] Successfully updated existing conversation status: {conversation_status}"
                )
            else:
                # Insert new ConversationStatus
                conversation_status = ConversationStatus(
                    group_id=group_id, **update_data
                )

                # Insert new Lite
                try:
                    conversation_status_lite = self._conversation_status_to_lite(
                        conversation_status
                    )
                    await conversation_status_lite.create(session=session)

                    # Copy generated ID and audit fields back
                    conversation_status.id = conversation_status_lite.id
                    conversation_status.created_at = conversation_status_lite.created_at
                    conversation_status.updated_at = conversation_status_lite.updated_at

                    logger.info(
                        f"Created conversation status: group_id={group_id}"
                    )
                    print(
                        f"[ConversationStatusRawRepository] Successfully created new conversation status: {conversation_status}"
                    )
                except Exception as create_error:
                    # Handle duplicate key error (concurrent case)
                    error_str = str(create_error)
                    if "E11000" in error_str and "duplicate key" in error_str:
                        logger.warning(
                            "⚠️  Concurrent creation conflict, re-lookup and update: group_id=%s",
                            group_id,
                        )

                        # Duplicate key error means another thread has already created the record, re-lookup and update
                        retry_lite = await self.model.find_one(
                            {"group_id": group_id}, session=session
                        )

                        if retry_lite:
                            # Reconstruct and update
                            retry_full = await self._conversation_status_lite_to_full(retry_lite)
                            if retry_full:
                                for key, value in update_data.items():
                                    if hasattr(retry_full, key):
                                        setattr(retry_full, key, value)

                                await retry_lite.save(session=session)
                                retry_full.created_at = retry_lite.created_at
                                retry_full.updated_at = retry_lite.updated_at

                                conversation_status = retry_full
                                logger.debug(
                                    "✅ Successfully updated after concurrency conflict: group_id=%s",
                                    group_id,
                                )
                                print(
                                    f"[ConversationStatusRawRepository] Successfully updated after concurrency conflict: {conversation_status}"
                                )
                            else:
                                logger.error(
                                    "❌ Failed to reconstruct after concurrency conflict: group_id=%s",
                                    group_id,
                                )
                                return None
                        else:
                            logger.error(
                                "❌ Still unable to find record after concurrency conflict: group_id=%s",
                                group_id,
                            )
                            return None
                    else:
                        # Other types of creation errors, re-raise
                        raise create_error

            # Write to KV-Storage (always full ConversationStatus)
            kv_storage = self._get_kv_storage()
            if kv_storage:
                try:
                    json_value = conversation_status.model_dump_json(
                        by_alias=True, exclude_none=False
                    )
                    success = await kv_storage.put(
                        key=str(conversation_status.id), value=json_value
                    )
                    if success:
                        logger.debug(f"✅ KV-Storage write success: {conversation_status.id}")
                    else:
                        logger.error(f"⚠️  KV-Storage write failed: {conversation_status.id}")
                        return None
                except Exception as kv_error:
                    logger.error(
                        f"⚠️  KV-Storage write error: {conversation_status.id}: {kv_error}"
                    )
                    return None

            return conversation_status
        except Exception as e:
            logger.error("❌ Failed to update or create conversation status: %s", e)
            return None

    # ==================== Statistics Methods ====================

    async def count_by_group_id(
        self, group_id: str, session: Optional[AsyncClientSession] = None
    ) -> int:
        """Count the number of conversation statuses for a specified group"""
        try:
            count = await self.model.find(
                {"group_id": group_id}, session=session
            ).count()
            logger.debug(
                "✅ Successfully counted conversation statuses: group_id=%s, count=%d",
                group_id,
                count,
            )
            return count
        except Exception as e:
            logger.error("❌ Failed to count conversation statuses: %s", e)
            return 0
