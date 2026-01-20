"""
ConversationMeta Lite Model - Minimal MongoDB Storage

Lightweight ConversationMeta model containing only indexed and query fields.
Used to minimize MongoDB storage - only stores indexed fields for queries.
Complete ConversationMeta data is stored in KV-Storage.
"""

from datetime import datetime
from typing import Optional
from core.oxm.mongo.document_base import DocumentBase
from core.oxm.mongo.audit_base import AuditBase
from pydantic import Field, ConfigDict
from pymongo import IndexModel, ASCENDING, DESCENDING


class ConversationMetaLite(DocumentBase, AuditBase):
    """
    ConversationMeta Lite Model - Minimal storage version

    Contains only indexed and query fields for MongoDB.
    Full ConversationMeta data is stored in KV-Storage.

    Note: Inherits from AuditBase to automatically manage created_at/updated_at timestamps.
    These audit fields are stored in both MongoDB (for queries) and KV-Storage (for full data).
    """

    # Core indexed fields
    group_id: Optional[str] = Field(
        default=None,
        description="Group ID, used to associate a group of conversations. When None, represents default settings.",
    )
    scene: str = Field(
        ...,
        description="Scene identifier, used to distinguish different application scenarios",
    )
    conversation_created_at: str = Field(
        ..., description="Conversation creation time, ISO format string"
    )

    model_config = ConfigDict(
        collection="conversation_metas",
        validate_assignment=True,
        json_encoders={datetime: lambda dt: dt.isoformat()},
    )

    class Settings:
        """Beanie settings"""

        name = "conversation_metas"
        indexes = [
            IndexModel(
                [("conversation_created_at", ASCENDING)],
                name="idx_conversation_created_at",
            ),
            # Creation time index
            IndexModel([("created_at", DESCENDING)], name="idx_created_at"),
            # Update time index
            IndexModel([("updated_at", DESCENDING)], name="idx_updated_at"),
            IndexModel(
                [("group_id", ASCENDING)], name="idx_group_id_unique", unique=True
            ),
        ]
        validate_on_save = True
        use_state_management = True


__all__ = ["ConversationMetaLite"]
