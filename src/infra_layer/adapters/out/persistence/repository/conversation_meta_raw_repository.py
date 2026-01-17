"""
ConversationMeta Raw Repository

Provides database operation interfaces for conversation metadata
"""

import logging
from typing import Optional, List, Dict, Any
from pymongo.asynchronous.client_session import AsyncClientSession

from core.oxm.mongo.base_repository import BaseRepository
from core.di.decorators import repository
from core.di import get_bean_by_type
from infra_layer.adapters.out.persistence.document.memory.conversation_meta import (
    ConversationMeta,
)
from infra_layer.adapters.out.persistence.document.memory.conversation_meta_lite import (
    ConversationMetaLite,
)
from infra_layer.adapters.out.persistence.kv_storage.kv_storage_interface import (
    KVStorageInterface,
)

logger = logging.getLogger(__name__)

# Allowed scene enum values
ALLOWED_SCENES = ["assistant", "companion"]


@repository("conversation_meta_raw_repository", primary=True)
class ConversationMetaRawRepository(BaseRepository[ConversationMetaLite]):
    """
    Raw repository layer for conversation metadata

    Provides basic database operations for conversation metadata
    """

    def __init__(self):
        """Initialize repository"""
        super().__init__(ConversationMetaLite)

        # Inject KV-Storage with graceful degradation
        self._kv_storage: Optional[KVStorageInterface] = None
        try:
            self._kv_storage = get_bean_by_type(KVStorageInterface)
            logger.info("✅ ConversationMeta KV-Storage initialized successfully")
        except Exception as e:
            logger.error(f"⚠️ ConversationMeta KV-Storage not available: {e}")
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

    def _conversation_meta_to_lite(
        self, conversation_meta: ConversationMeta
    ) -> ConversationMetaLite:
        """
        Convert full ConversationMeta to ConversationMetaLite (only indexed fields).

        Args:
            conversation_meta: Full ConversationMeta object

        Returns:
            ConversationMetaLite with only indexed fields

        Note:
            Audit fields (created_at/updated_at) are not copied here.
            They will be automatically set by AuditBase during insert/update operations.
        """
        return ConversationMetaLite(
            id=conversation_meta.id,
            group_id=conversation_meta.group_id,
            scene=conversation_meta.scene,
        )

    async def _conversation_meta_lite_to_full(
        self, lite: ConversationMetaLite
    ) -> Optional[ConversationMeta]:
        """
        Reconstruct full ConversationMeta object from KV-Storage.
        MongoDB is ONLY used for querying and getting _id.

        Args:
            lite: ConversationMetaLite from MongoDB query

        Returns:
            Full ConversationMeta object from KV-Storage or None
        """
        if not lite:
            return None

        kv_storage = self._get_kv_storage()
        if not kv_storage:
            logger.error("❌ KV-Storage unavailable, cannot reconstruct ConversationMeta")
            return None

        # Get from KV-Storage (source of truth)
        conversation_meta_id = str(lite.id)
        kv_json = await kv_storage.get(conversation_meta_id)

        if kv_json:
            try:
                full_conversation_meta = ConversationMeta.model_validate_json(kv_json)
                return full_conversation_meta
            except Exception as e:
                logger.error(
                    f"❌ Failed to deserialize ConversationMeta: {conversation_meta_id}, error: {e}"
                )
                return None
        else:
            logger.warning(
                f"⚠️ ConversationMeta not found in KV-Storage: {conversation_meta_id}"
            )
            return None

    def _validate_scene(self, scene: str) -> bool:
        """
        Validate if scene is valid

        Args:
            scene: Scene identifier

        Returns:
            bool: Returns True if valid, False otherwise
        """
        if scene not in ALLOWED_SCENES:
            logger.warning(
                "❌ Invalid scene value: %s, allowed values: %s", scene, ALLOWED_SCENES
            )
            return False
        return True

    async def get_by_group_id(
        self, group_id: str, session: Optional[AsyncClientSession] = None
    ) -> Optional[ConversationMeta]:
        """
        Get conversation metadata by group ID

        Args:
            group_id: Group ID
            session: Optional MongoDB session, used for transaction support

        Returns:
            Conversation metadata object or None
        """
        try:
            # Query MongoDB Lite model first
            lite_result = await self.model.find_one(
                {"group_id": group_id}, session=session
            )
            if not lite_result:
                logger.debug(
                    "ℹ️  ConversationMeta not found: group_id=%s", group_id
                )
                return None

            # Reconstruct from KV-Storage
            full_conversation_meta = await self._conversation_meta_lite_to_full(
                lite_result
            )
            if full_conversation_meta:
                logger.debug(
                    "✅ Retrieved ConversationMeta successfully: group_id=%s", group_id
                )
            return full_conversation_meta
        except Exception as e:
            logger.error(
                "❌ Failed to retrieve conversation metadata by group_id: %s", e
            )
            return None

    async def list_by_scene(
        self,
        scene: str,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
        session: Optional[AsyncClientSession] = None,
    ) -> List[ConversationMeta]:
        """
        Get list of conversation metadata by scene identifier

        Args:
            scene: Scene identifier
            limit: Limit on number of returned items
            skip: Number of items to skip
            session: Optional MongoDB session

        Returns:
            List of conversation metadata
        """
        try:
            # Validate scene field
            if not self._validate_scene(scene):
                logger.warning(
                    "❌ Invalid scene value when querying conversation metadata list: %s, allowed values: %s",
                    scene,
                    ALLOWED_SCENES,
                )
                return []

            # Query MongoDB Lite models
            query = self.model.find({"scene": scene}, session=session)
            if skip:
                query = query.skip(skip)
            if limit:
                query = query.limit(limit)

            lite_results = await query.to_list()

            # Reconstruct full objects from KV-Storage
            full_metas = []
            for lite in lite_results:
                full_meta = await self._conversation_meta_lite_to_full(lite)
                if full_meta:
                    full_metas.append(full_meta)

            logger.debug(
                "✅ Successfully retrieved conversation metadata list by scene: scene=%s, count=%d",
                scene,
                len(full_metas),
            )
            return full_metas
        except Exception as e:
            logger.error(
                "❌ Failed to retrieve conversation metadata list by scene: %s", e
            )
            return []

    async def create_conversation_meta(
        self,
        conversation_meta: ConversationMeta,
        session: Optional[AsyncClientSession] = None,
    ) -> Optional[ConversationMeta]:
        """
        Create new conversation metadata

        Args:
            conversation_meta: Conversation metadata object
            session: Optional MongoDB session, used for transaction support

        Returns:
            Created conversation metadata object or None
        """
        try:
            # Validate scene field
            if not self._validate_scene(conversation_meta.scene):
                logger.error(
                    "❌ Failed to create conversation metadata: invalid scene value: %s, allowed values: %s",
                    conversation_meta.scene,
                    ALLOWED_SCENES,
                )
                return None

            # Insert new Lite
            conversation_meta_lite = self._conversation_meta_to_lite(conversation_meta)
            await conversation_meta_lite.insert(session=session)

            # Copy generated ID and audit fields back
            conversation_meta.id = conversation_meta_lite.id
            conversation_meta.created_at = conversation_meta_lite.created_at
            conversation_meta.updated_at = conversation_meta_lite.updated_at

            # Write to KV-Storage (always full ConversationMeta)
            kv_storage = self._get_kv_storage()
            if kv_storage:
                try:
                    json_value = conversation_meta.model_dump_json(
                        by_alias=True, exclude_none=False
                    )
                    success = await kv_storage.put(
                        key=str(conversation_meta.id), value=json_value
                    )
                    if success:
                        logger.debug(
                            f"✅ KV-Storage write success: {conversation_meta.id}"
                        )
                    else:
                        logger.error(
                            f"⚠️  KV-Storage write failed: {conversation_meta.id}"
                        )
                        return None
                except Exception as kv_error:
                    logger.error(
                        f"⚠️  KV-Storage write error: {conversation_meta.id}: {kv_error}"
                    )
                    return None

            logger.info(
                "✅ Successfully created conversation metadata: group_id=%s, scene=%s",
                conversation_meta.group_id,
                conversation_meta.scene,
            )
            return conversation_meta
        except Exception as e:
            logger.error(
                "❌ Failed to create conversation metadata: %s", e, exc_info=True
            )
            return None

    async def update_by_group_id(
        self,
        group_id: str,
        update_data: Dict[str, Any],
        session: Optional[AsyncClientSession] = None,
    ) -> Optional[ConversationMeta]:
        """
        Update conversation metadata by group ID

        Args:
            group_id: Group ID
            update_data: Dictionary of update data
            session: Optional MongoDB session, used for transaction support

        Returns:
            Updated conversation metadata object or None
        """
        try:
            # If scene is in update data, validate first
            if "scene" in update_data and not self._validate_scene(
                update_data["scene"]
            ):
                logger.error(
                    "❌ Failed to update conversation metadata: invalid scene value: %s, allowed values: %s",
                    update_data["scene"],
                    ALLOWED_SCENES,
                )
                return None

            # Query MongoDB Lite model first
            existing_lite = await self.model.find_one(
                {"group_id": group_id}, session=session
            )
            if not existing_lite:
                return None

            # Reconstruct existing from KV-Storage
            existing = await self._conversation_meta_lite_to_full(existing_lite)
            if not existing:
                logger.error(
                    f"Failed to reconstruct existing conversation meta from KV-Storage: group_id={group_id}"
                )
                return None

            # Update fields
            for key, value in update_data.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)

            # Update Lite in MongoDB (for indexed fields)
            if "group_id" in update_data:
                existing_lite.group_id = update_data["group_id"]
            if "scene" in update_data:
                existing_lite.scene = update_data["scene"]
            await existing_lite.save(session=session)

            # Copy updated audit fields back
            existing.created_at = existing_lite.created_at
            existing.updated_at = existing_lite.updated_at

            # Write to KV-Storage
            kv_storage = self._get_kv_storage()
            if kv_storage:
                try:
                    json_value = existing.model_dump_json(
                        by_alias=True, exclude_none=False
                    )
                    success = await kv_storage.put(
                        key=str(existing.id), value=json_value
                    )
                    if success:
                        logger.debug(f"✅ KV-Storage write success: {existing.id}")
                    else:
                        logger.error(f"⚠️  KV-Storage write failed: {existing.id}")
                        return None
                except Exception as kv_error:
                    logger.error(
                        f"⚠️  KV-Storage write error: {existing.id}: {kv_error}"
                    )
                    return None

            logger.debug(
                "✅ Successfully updated conversation metadata by group_id: %s",
                group_id,
            )
            return existing
        except Exception as e:
            logger.error(
                "❌ Failed to update conversation metadata by group_id: %s",
                e,
                exc_info=True,
            )
            return None

    async def upsert_by_group_id(
        self,
        group_id: str,
        conversation_data: Dict[str, Any],
        session: Optional[AsyncClientSession] = None,
    ) -> Optional[ConversationMeta]:
        """
        Update or insert conversation metadata by group ID

        Uses MongoDB atomic upsert operation to avoid concurrency race conditions

        Args:
            group_id: Group ID
            conversation_data: Conversation metadata dictionary
            session: Optional MongoDB session

        Returns:
            Updated or created conversation metadata object
        """
        try:
            # If data contains scene, validate first
            if "scene" in conversation_data and not self._validate_scene(
                conversation_data["scene"]
            ):
                logger.error(
                    "❌ Failed to upsert conversation metadata: invalid scene value: %s, allowed values: %s",
                    conversation_data["scene"],
                    ALLOWED_SCENES,
                )
                return None

            # Check if already exists
            existing_lite = await self.model.find_one(
                {"group_id": group_id}, session=session
            )

            # Prepare full ConversationMeta object
            if existing_lite:
                # Update: reconstruct existing from KV-Storage
                existing = await self._conversation_meta_lite_to_full(existing_lite)
                if not existing:
                    logger.error(
                        f"Failed to reconstruct existing conversation meta from KV-Storage: group_id={group_id}"
                    )
                    return None

                # Update fields
                for key, value in conversation_data.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)

                # Update Lite in MongoDB (for indexed fields)
                if "group_id" in conversation_data:
                    existing_lite.group_id = conversation_data["group_id"]
                if "scene" in conversation_data:
                    existing_lite.scene = conversation_data["scene"]
                await existing_lite.save(session=session)

                # Copy updated audit fields back
                existing.created_at = existing_lite.created_at
                existing.updated_at = existing_lite.updated_at

                conversation_meta = existing
                logger.debug(
                    f"Updated conversation metadata: group_id={group_id}"
                )
            else:
                # Insert new ConversationMeta
                conversation_meta = ConversationMeta(
                    group_id=group_id, **conversation_data
                )

                # Insert new Lite
                conversation_meta_lite = self._conversation_meta_to_lite(
                    conversation_meta
                )
                await conversation_meta_lite.insert(session=session)

                # Copy generated ID and audit fields back
                conversation_meta.id = conversation_meta_lite.id
                conversation_meta.created_at = conversation_meta_lite.created_at
                conversation_meta.updated_at = conversation_meta_lite.updated_at

                logger.info(
                    f"Created conversation metadata: group_id={group_id}"
                )

            # Write to KV-Storage (always full ConversationMeta)
            kv_storage = self._get_kv_storage()
            if kv_storage:
                try:
                    json_value = conversation_meta.model_dump_json(
                        by_alias=True, exclude_none=False
                    )
                    success = await kv_storage.put(
                        key=str(conversation_meta.id), value=json_value
                    )
                    if success:
                        logger.debug(f"✅ KV-Storage write success: {conversation_meta.id}")
                    else:
                        logger.error(f"⚠️  KV-Storage write failed: {conversation_meta.id}")
                        return None
                except Exception as kv_error:
                    logger.error(
                        f"⚠️  KV-Storage write error: {conversation_meta.id}: {kv_error}"
                    )
                    return None

            return conversation_meta
        except Exception as e:
            logger.error(
                "❌ Failed to upsert conversation metadata: %s", e, exc_info=True
            )
            return None

    async def delete_by_group_id(
        self, group_id: str, session: Optional[AsyncClientSession] = None
    ) -> bool:
        """
        Delete conversation metadata by group ID

        Args:
            group_id: Group ID
            session: Optional MongoDB session

        Returns:
            Whether deletion was successful
        """
        try:
            # Get the lite object first to obtain ID for KV-Storage deletion
            lite = await self.model.find_one({"group_id": group_id}, session=session)
            if not lite:
                return False

            conversation_meta_id = str(lite.id)

            # Delete from MongoDB
            result = await lite.delete(session=session)
            if result:
                # Delete from KV-Storage
                kv_storage = self._get_kv_storage()
                if kv_storage:
                    try:
                        await kv_storage.delete(conversation_meta_id)
                    except Exception as kv_error:
                        logger.error(f"⚠️  KV-Storage delete error: {kv_error}")

                logger.info(
                    "✅ Successfully deleted conversation metadata: group_id=%s",
                    group_id,
                )
                return True
            return False
        except Exception as e:
            logger.error("❌ Failed to delete conversation metadata: %s", e)
            return False
