# -*- coding: utf-8 -*-
"""
MemoryRequestLog Lite Model - Minimal MongoDB Storage

Lightweight MemoryRequestLog model containing only indexed and query fields.
Used to minimize MongoDB storage - only stores indexed fields for queries.
Complete MemoryRequestLog data is stored in KV-Storage.
"""

from datetime import datetime
from typing import Optional
from core.oxm.mongo.document_base import DocumentBase
from core.oxm.mongo.audit_base import AuditBase
from pydantic import Field, ConfigDict
from pymongo import IndexModel, ASCENDING, DESCENDING


class MemoryRequestLogLite(DocumentBase, AuditBase):
    """
    MemoryRequestLog Lite Model - Minimal storage version

    Contains only indexed and query fields for MongoDB.
    Full MemoryRequestLog data is stored in KV-Storage.

    Note: Inherits from AuditBase to automatically manage created_at/updated_at timestamps.
    These audit fields are stored in both MongoDB (for queries) and KV-Storage (for full data).
    """

    # Core indexed fields
    group_id: str = Field(..., description="Conversation group ID")
    request_id: str = Field(..., description="Request ID")
    user_id: Optional[str] = Field(default=None, description="User ID")
    event_id: Optional[str] = Field(default=None, description="Original event ID")
    message_id: Optional[str] = Field(default=None, description="Message ID")
    message_create_time: Optional[str] = Field(
        default=None, description="Message creation time (ISO 8601 format)"
    )
    sync_status: int = Field(
        default=-1,
        description="Sync status: -1=log record, 0=window accumulating, 1=already used",
    )

    model_config = ConfigDict(
        collection="memory_request_logs",
        validate_assignment=True,
        json_encoders={datetime: lambda dt: dt.isoformat()},
    )

    class Settings:
        """Beanie settings"""

        name = "memory_request_logs"
        indexes = [
            IndexModel([("group_id", ASCENDING), ("created_at", DESCENDING)]),
            IndexModel([("request_id", ASCENDING)]),
            IndexModel([("user_id", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
            IndexModel([("event_id", ASCENDING)]),
            IndexModel([("message_id", ASCENDING)]),
            IndexModel([("group_id", ASCENDING), ("message_create_time", DESCENDING)]),
            IndexModel([("group_id", ASCENDING), ("sync_status", ASCENDING)]),
            IndexModel(
                [
                    ("group_id", ASCENDING),
                    ("user_id", ASCENDING),
                    ("sync_status", ASCENDING),
                ]
            ),
            IndexModel([("updated_at", DESCENDING)], name="idx_updated_at"),
        ]
        validate_on_save = True
        use_state_management = True


__all__ = ["MemoryRequestLogLite"]
