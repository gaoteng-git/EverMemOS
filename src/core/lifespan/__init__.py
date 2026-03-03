# Import all lifespan providers to ensure they are registered with DI container
from .kv_storage_lifespan import KVStorageLifespan  # noqa: F401

__all__ = ["KVStorageLifespan"]
