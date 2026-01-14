"""
EpisodicMemory Lite Model - Minimal MongoDB Storage

Lightweight EpisodicMemory model containing only indexed and query fields.
Used to minimize MongoDB storage - only stores indexed fields for queries.
Complete EpisodicMemory data is stored in KV-Storage.
"""

from datetime import datetime
from typing import List, Optional
from beanie import Indexed
from core.oxm.mongo.document_base import DocumentBase
from pydantic import Field, ConfigDict
from pymongo import IndexModel, ASCENDING, DESCENDING
from beanie import PydanticObjectId


class EpisodicMemoryLite(DocumentBase):
    """
    EpisodicMemory Lite Model - Minimal storage version

    Contains only indexed and query fields for MongoDB.
    Full EpisodicMemory data is stored in KV-Storage as backup.

    Note: Does not inherit from AuditBase - created_at/updated_at are managed manually
    and stored in both MongoDB (for queries) and KV-Storage (for full data).
    """

    # Core indexed fields
    user_id: Optional[str] = Field(
        default=None, description="The individual involved, None indicates group memory"
    )
    group_id: Optional[str] = Field(default=None, description="Group ID")
    timestamp: Indexed(datetime) = Field(..., description="Occurrence time (timestamp)")

    # Additional query fields
    keywords: Optional[List[str]] = Field(default=None, description="Keywords")
    linked_entities: Optional[List[str]] = Field(
        default=None, description="Associated entity IDs"
    )

    # Audit fields (indexed, managed manually)
    created_at: Indexed(datetime) = Field(
        default=None, description="Creation time"
    )
    updated_at: Indexed(datetime) = Field(
        default=None, description="Last update time"
    )

    model_config = ConfigDict(
        # Collection name (same as full EpisodicMemory)
        collection="episodic_memories",
        validate_assignment=True,
        json_encoders={datetime: lambda dt: dt.isoformat()},
    )

    @property
    def event_id(self) -> Optional[PydanticObjectId]:
        return self.id

    class Settings:
        """Beanie settings"""

        name = "episodic_memories"

        # Same indexes as full EpisodicMemory
        indexes = [
            # Composite index on user ID and timestamp
            IndexModel(
                [("user_id", ASCENDING), ("timestamp", DESCENDING)],
                name="idx_user_timestamp",
            ),
            # Composite index on group ID and timestamp
            IndexModel(
                [("group_id", ASCENDING), ("timestamp", DESCENDING)],
                name="idx_group_timestamp",
            ),
            # Index on keywords
            IndexModel([("keywords", ASCENDING)], name="idx_keywords", sparse=True),
            # Index on linked entities
            IndexModel(
                [("linked_entities", ASCENDING)],
                name="idx_linked_entities",
                sparse=True,
            ),
            # Index on audit fields
            IndexModel([("created_at", DESCENDING)], name="idx_created_at"),
            IndexModel([("updated_at", DESCENDING)], name="idx_updated_at"),
        ]

        validate_on_save = True
        use_state_management = True


__all__ = ["EpisodicMemoryLite"]
