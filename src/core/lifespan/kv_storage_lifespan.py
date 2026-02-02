"""
KV-Storage Lifespan Provider

Initializes and manages KV-Storage lifecycle based on environment configuration.
Supports InMemoryKVStorage (development) and ZeroGKVStorage (production).
"""

import os
from core.observation.logger import get_logger
from core.di.decorators import component
from core.lifespan.lifespan_interface import LifespanProvider
from core.di.utils import register_primary
from infra_layer.adapters.out.persistence.kv_storage.kv_storage_interface import (
    KVStorageInterface,
)

logger = get_logger(__name__)


@component("kv_storage_lifespan", primary=True)
class KVStorageLifespan(LifespanProvider):
    """
    KV-Storage lifecycle management

    Reads KV_STORAGE_TYPE environment variable to determine implementation:
    - "inmemory": InMemoryKVStorage (default, for development/testing)
    - "redis": RedisKVStorage (for production with Redis backend)
    - "zerog": ZeroGKVStorage (for production with 0G-Storage backend)
    """

    def __init__(self):
        super().__init__(name="kv_storage_lifespan", order=5)
        self.kv_storage = None

    async def startup(self, app) -> None:
        """
        Initialize KV-Storage based on environment configuration

        Environment Variables:
            KV_STORAGE_TYPE: "inmemory", "redis", or "zerog" (default: "inmemory")

        For ZeroG Storage, also requires:
            ZEROG_NODES: Comma-separated write nodes
            ZEROG_READ_NODE: Read node URL
            ZEROG_RPC_URL: RPC endpoint URL
            ZEROG_STREAM_ID: Unified stream ID
            ZEROG_WALLET_KEY: Wallet private key
            ZEROG_TIMEOUT: Command timeout in seconds (optional, default: 30)
            ZEROG_MAX_RETRIES: Max retry attempts (optional, default: 3)
        """
        kv_type = os.getenv("KV_STORAGE_TYPE", "inmemory").lower()

        try:
            if kv_type == "zerog":
                logger.info("🚀 Initializing 0G-Storage KV-Storage...")

                # Import here to avoid circular dependency
                from infra_layer.adapters.out.persistence.kv_storage.zerog_kv_storage import (
                    ZeroGKVStorage,
                )

                # Read configuration from environment variables
                nodes = os.getenv("ZEROG_NODES")
                stream_id = os.getenv("ZEROG_STREAM_ID")
                rpc_url = os.getenv("ZEROG_RPC_URL")
                read_node = os.getenv("ZEROG_READ_NODE")

                # Validate required configuration
                missing_vars = []
                if not nodes:
                    missing_vars.append("ZEROG_NODES")
                if not stream_id:
                    missing_vars.append("ZEROG_STREAM_ID")
                if not rpc_url:
                    missing_vars.append("ZEROG_RPC_URL")
                if not read_node:
                    missing_vars.append("ZEROG_READ_NODE")

                if missing_vars:
                    raise ValueError(
                        f"Missing required 0G-Storage configuration: {', '.join(missing_vars)}. "
                        f"Please set these environment variables or check .env file."
                    )

                # Optional parameters with defaults
                timeout = int(os.getenv("ZEROG_TIMEOUT", "30"))
                max_retries = int(os.getenv("ZEROG_MAX_RETRIES", "3"))

                # Create ZeroGKVStorage instance
                # Note: ZEROG_WALLET_KEY is read inside ZeroGKVStorage.__init__
                kv_storage = ZeroGKVStorage(
                    nodes=nodes,
                    stream_id=stream_id,
                    rpc_url=rpc_url,
                    read_node=read_node,
                    timeout=timeout,
                    max_retries=max_retries,
                )

                logger.info(
                    f"✅ 0G-Storage KV-Storage initialized successfully\n"
                    f"   Stream ID: {stream_id}\n"
                    f"   Nodes: {nodes.split(',')[0]}... (+{len(nodes.split(',')) - 1} more)\n"
                    f"   Read Node: {read_node}\n"
                    f"   Timeout: {timeout}s, Max Retries: {max_retries}"
                )

            elif kv_type == "redis":
                logger.info("🚀 Initializing Redis KV-Storage...")

                # Import here to avoid circular dependency
                from infra_layer.adapters.out.persistence.kv_storage.redis_kv_storage import (
                    RedisKVStorage,
                )

                # RedisKVStorage uses RedisProvider from DI container
                # No additional configuration needed here
                kv_storage = RedisKVStorage()

                logger.info(
                    "✅ Redis KV-Storage initialized successfully\n"
                    "   (Using RedisProvider from DI container)"
                )

            else:
                # Default: InMemoryKVStorage
                if kv_type != "inmemory":
                    logger.warning(
                        f"⚠️  Unknown KV_STORAGE_TYPE '{kv_type}', falling back to 'inmemory'"
                    )

                logger.info("🚀 Initializing In-Memory KV-Storage...")

                from infra_layer.adapters.out.persistence.kv_storage.in_memory_kv_storage import (
                    InMemoryKVStorage,
                )

                kv_storage = InMemoryKVStorage()
                logger.info(
                    "✅ In-Memory KV-Storage initialized (data will be lost on restart)"
                )

            # Register to DI container as primary KVStorageInterface implementation
            register_primary(KVStorageInterface, kv_storage)
            self.kv_storage = kv_storage
            logger.info(
                f"✅ KV-Storage registered to DI container: {type(kv_storage).__name__}"
            )

        except Exception as e:
            logger.error(f"❌ Failed to initialize KV-Storage: {e}")
            raise

    async def shutdown(self, app) -> None:
        """Cleanup KV-Storage resources"""
        if self.kv_storage:
            logger.info(f"🔄 Shutting down KV-Storage: {type(self.kv_storage).__name__}")


__all__ = ["KVStorageLifespan"]
