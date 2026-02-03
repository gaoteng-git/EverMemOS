"""
Base data sync validator

Provides common data structures and utilities for data consistency validation.
"""

from dataclasses import dataclass
from typing import Set


@dataclass
class SyncResult:
    """Result of a sync operation"""

    doc_type: str
    target: str
    total_checked: int
    missing_count: int
    synced_count: int
    error_count: int
    elapsed_time: float

    def __str__(self) -> str:
        """String representation for logging"""
        if self.synced_count > 0:
            return (
                f"{self.doc_type} ({self.target}): "
                f"Found {self.missing_count} missing docs, "
                f"synced {self.synced_count}, "
                f"errors {self.error_count} "
                f"({self.elapsed_time:.2f}s)"
            )
        else:
            return (
                f"{self.doc_type} ({self.target}): "
                f"All {self.total_checked} docs consistent"
            )


class DataSyncValidator:
    """Base validator for data consistency checking"""

    @staticmethod
    def find_missing_ids(mongo_ids: Set[str], target_ids: Set[str]) -> Set[str]:
        """
        Find IDs that exist in MongoDB but not in target

        Args:
            mongo_ids: Set of MongoDB document IDs
            target_ids: Set of target (Milvus/ES) document IDs

        Returns:
            Set of missing IDs
        """
        return mongo_ids - target_ids
