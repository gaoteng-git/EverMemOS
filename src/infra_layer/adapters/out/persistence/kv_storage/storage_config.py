"""
Global Storage Configuration

Global configuration for dual-storage behavior across all data types.
Controls whether MongoDB stores full documents or only indexed fields.
"""

import os
from typing import Optional


class StorageConfig:
    """
    Global storage configuration singleton

    Controls the storage strategy for all data types (MemCell, etc.):
    - FULL mode: MongoDB stores all fields, KV-Storage validation enabled
    - LITE mode: MongoDB stores only indexed/query fields, no validation

    Environment Variable:
        FULL_STORAGE_MODE: "true" or "false" (default: "true")
    """

    _instance: Optional['StorageConfig'] = None
    _full_storage_mode: bool = True

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize configuration from environment variable"""
        env_value = os.getenv("FULL_STORAGE_MODE", "true").lower()
        self._full_storage_mode = env_value in ("true", "1", "yes", "on")

    @property
    def is_full_storage_mode(self) -> bool:
        """
        Check if full storage mode is enabled

        Returns:
            True: MongoDB stores all fields, KV-Storage validation enabled
            False: MongoDB stores only indexed fields, no KV-Storage validation
        """
        return self._full_storage_mode

    @property
    def should_validate_kv_consistency(self) -> bool:
        """
        Check if KV-Storage consistency validation should be performed

        Returns:
            True: Validate MongoDB <-> KV-Storage consistency
            False: Skip validation (lite mode)
        """
        return self._full_storage_mode

    def __repr__(self) -> str:
        mode = "FULL" if self._full_storage_mode else "LITE"
        return f"StorageConfig(mode={mode}, validate_kv={self.should_validate_kv_consistency})"


# Global singleton instance
_config = StorageConfig()


def is_full_storage_mode() -> bool:
    """Check if full storage mode is enabled"""
    return _config.is_full_storage_mode


def should_validate_kv_consistency() -> bool:
    """Check if KV-Storage consistency validation should be performed"""
    return _config.should_validate_kv_consistency


def get_storage_config() -> StorageConfig:
    """Get global storage configuration instance"""
    return _config


__all__ = [
    "StorageConfig",
    "is_full_storage_mode",
    "should_validate_kv_consistency",
    "get_storage_config",
]
