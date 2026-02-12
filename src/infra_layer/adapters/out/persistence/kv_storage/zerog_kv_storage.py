"""
0G-Storage based KV-Storage implementation

Uses 0g-storage Python SDK for storage operations.
All values are UTF-8 encoded as bytes.

Key Format: {collection_name}:{document_id}
Example: "episodic_memories:6979da5797f9041fc0aa063f"

Environment Variables Required:
- ZEROG_WALLET_KEY: Wallet private key (IMPORTANT: Keep secure!)
"""

import asyncio
import json
import os
from typing import Optional, Dict, List
from core.observation.logger import get_logger
from core.di.decorators import component
from .kv_storage_interface import KVStorageInterface

# Import 0g-storage Python SDK
from zg_storage import EvmClient
from zg_storage.core.data import BytesDataSource
from zg_storage.indexer import IndexerClient
from zg_storage.kv import StreamDataBuilder, KvClient
from zg_storage.kv.types import create_tags
from zg_storage.transfer import NodeUploader, NodeUploaderConfig, UploadOption

logger = get_logger(__name__)


@component("zerog_kv_storage")
class ZeroGKVStorage(KVStorageInterface):
    """
    0G-Storage based KV-Storage implementation

    Uses 0g-storage Python SDK for storage operations.
    All values are UTF-8 encoded as bytes.

    Note:
    - All documents share a unified stream-id
    - Keys use format: {collection_name}:{document_id}
    - Delete is implemented as writing empty string
    """

    def __init__(
        self,
        nodes: str,                    # "http://35.236.80.213:5678,http://34.102.76.235:5678"
        stream_id: str,                # Unified stream ID for all collections
        rpc_url: str,                  # "https://evmrpc-testnet.0g.ai"
        read_node: str,                # "http://34.31.1.26:6789" (read operations)
        timeout: int = 30,             # Request timeout in seconds
        max_retries: int = 3,          # Max retry attempts
        use_indexer: bool = True,      # Use IndexerClient (True) or NodeUploader (False)
        indexer_url: Optional[str] = None,  # Indexer URL (required if use_indexer=True)
        flow_address: Optional[str] = None  # Flow contract address (required if use_indexer=True)
    ):
        self.nodes = nodes.split(',') if isinstance(nodes, str) else nodes
        self.stream_id = stream_id
        self.rpc_url = rpc_url
        self.read_node = read_node
        self.timeout = timeout
        self.max_retries = max_retries
        self.use_indexer = use_indexer
        self.indexer_url = indexer_url
        self.flow_address = flow_address

        # Validate indexer configuration
        if self.use_indexer:
            if not self.indexer_url:
                raise ValueError("indexer_url is required when use_indexer=True")
            if not self.flow_address:
                raise ValueError("flow_address is required when use_indexer=True")

        # Get wallet private key from environment variable (SECURE!)
        self.wallet_private_key = os.getenv('ZEROG_WALLET_KEY')
        if not self.wallet_private_key:
            raise ValueError("ZEROG_WALLET_KEY environment variable is required")

        # Initialize EVM client
        self.evm_client = EvmClient(
            rpc_url=self.rpc_url,
            private_key=self.wallet_private_key
        )

        # Initialize KV client for read operations
        self.kv_client = KvClient(self.read_node, timeout=float(self.timeout))

        # Initialize uploader (IndexerClient or NodeUploader)
        if self.use_indexer:
            self.uploader = IndexerClient(
                self.indexer_url,
                evm_client=self.evm_client,
                flow_address=self.flow_address
            )
            logger.info(f"✅ Using IndexerClient: {self.indexer_url}")
        else:
            cfg = NodeUploaderConfig(
                nodes=self.nodes,
                evm_client=self.evm_client,
                flow_address=self.flow_address,
                rpc_timeout=float(self.timeout)
            )
            self.uploader = NodeUploader.from_config(cfg)
            logger.info(f"✅ Using NodeUploader: {self.nodes[0]}...")

        # Batch mode state
        self._batch_mode = False
        self._batch_builder: Optional[StreamDataBuilder] = None
        self._batch_operations: List[tuple] = []  # List of (key, value) tuples

        # Concurrency control: lock to prevent parallel batch operations
        # Multiple concurrent POST requests share the same KVStorage instance (singleton)
        # This lock ensures only one batch operation at a time
        self._batch_lock = asyncio.Lock()

        logger.info(
            f"✅ ZeroGKVStorage initialized with Python SDK\n"
            f"   Stream ID: {stream_id}\n"
            f"   RPC URL: {rpc_url}\n"
            f"   Read Node: {read_node}\n"
            f"   Timeout: {timeout}s"
        )


    async def _upload_builder(self, builder: StreamDataBuilder) -> tuple:
        """
        Upload a StreamDataBuilder to 0G-Storage

        This is a private helper method to reduce code duplication.
        Used by put(), delete(), batch_delete(), and commit_batch().

        Args:
            builder: StreamDataBuilder with staged operations

        Returns:
            Tuple of (tx, root) from upload operation

        Raises:
            Exception if upload fails
        """
        # Build and encode the stream data
        stream_data = builder.build(sorted_items=True)
        payload = stream_data.encode()
        tags = create_tags(builder.stream_ids(), sorted_ids=True)

        # Upload option
        opt = UploadOption(tags=tags)

        # Upload using SDK in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        tx, root = await loop.run_in_executor(
            None,
            lambda: self.uploader.upload(
                file_path=BytesDataSource(payload),
                tags=tags,
                option=opt
            )
        )

        return tx, root


    async def get(self, key: str) -> Optional[str]:
        """
        Get value by key using Python SDK

        Args:
            key: Full key including collection prefix (e.g., "episodic_memories:123")

        Returns:
            JSON string or None if not found
        """
        try:
            # Convert key to bytes
            key_bytes = key.encode('utf-8')

            # Call SDK in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            value_bytes = await loop.run_in_executor(
                None,
                self.kv_client.get_value_bytes,
                self.stream_id,
                key_bytes
            )

            if value_bytes is None or len(value_bytes) == 0:
                # Key not found or deleted
                return None

            # Decode bytes to UTF-8 string (JSON)
            json_value = value_bytes.decode('utf-8')
            logger.debug(f"✅ Get key: {key} ({len(json_value)} bytes)")
            return json_value

        except Exception as e:
            logger.error(f"❌ Failed to get key {key}: {e}")
            return None


    async def put(self, key: str, value: str) -> bool:
        """
        Store key-value pair using Python SDK

        In batch mode: stages the operation for later commit
        In normal mode: uploads immediately

        Args:
            key: Full key including collection prefix (e.g., "episodic_memories:123")
            value: JSON string to store

        Returns:
            True if successful (or staged in batch mode)
        """
        try:
            # Convert to bytes (UTF-8 encoding)
            key_bytes = key.encode('utf-8')
            value_bytes = value.encode('utf-8')

            # Batch mode: only stage the operation
            if self._batch_mode:
                if self._batch_builder is None:
                    logger.error("❌ Batch mode active but builder not initialized")
                    return False

                # Stage the operation
                self._batch_builder.set(
                    stream_id=self.stream_id,
                    key=key_bytes,
                    data=value_bytes
                )
                self._batch_operations.append((key, len(value)))
                logger.debug(f"📦 Staged key in batch: {key} ({len(value)} bytes)")
                return True

            # Normal mode: upload immediately
            # Build KV payload using StreamDataBuilder
            builder = StreamDataBuilder()
            builder.set(
                stream_id=self.stream_id,
                key=key_bytes,
                data=value_bytes
            )

            # Upload to 0G-Storage
            tx, root = await self._upload_builder(builder)
            logger.debug(f"✅ Put key: {key} ({len(value)} bytes), tx={tx}, root={root}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to put key {key}: {e}")
            return False


    async def delete(self, key: str) -> bool:
        """
        Delete by key (implemented as writing empty string) using Python SDK

        Args:
            key: Full key including collection prefix

        Returns:
            True if successful
        """
        try:
            # Warning: delete during batch mode may cause conflicts
            if self._batch_mode:
                logger.warning(
                    f"⚠️  delete() called during batch mode for key {key}. "
                    "This will create a separate upload operation and may conflict with batch commit."
                )

            # Delete by writing empty bytes
            key_bytes = key.encode('utf-8')
            empty_bytes = b''

            # Build KV payload with empty value
            builder = StreamDataBuilder()
            builder.set(
                stream_id=self.stream_id,
                key=key_bytes,
                data=empty_bytes
            )

            # Upload to 0G-Storage
            tx, root = await self._upload_builder(builder)
            logger.debug(f"✅ Delete key: {key}, tx={tx}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to delete key {key}: {e}")
            return False


    async def batch_get(self, keys: List[str]) -> Dict[str, str]:
        """
        Batch get values using Python SDK

        Args:
            keys: List of keys (each with collection prefix)

        Returns:
            Dict mapping key to JSON string
        """
        if not keys:
            return {}

        try:
            # Convert keys to bytes
            keys_bytes = [key.encode('utf-8') for key in keys]

            # Call SDK in thread pool
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None,
                self.kv_client.get_values,
                self.stream_id,
                keys_bytes
            )

            # data is Dict[bytes, bytes], convert to Dict[str, str]
            # and decode UTF-8 values to JSON strings
            result = {}
            for key_bytes, value_bytes in data.items():
                if value_bytes and len(value_bytes) > 0:
                    key_str = key_bytes.decode('utf-8')

                    # Decode UTF-8 bytes to JSON string
                    try:
                        json_value = value_bytes.decode('utf-8')
                        result[key_str] = json_value
                    except Exception as e:
                        logger.warning(f"⚠️  Failed to decode value for key {key_str}: {e}")
                        continue

            logger.debug(f"✅ Batch get {len(result)}/{len(keys)} keys")
            return result

        except Exception as e:
            logger.error(f"❌ Failed to batch get {len(keys)} keys: {e}")
            return {}


    async def batch_delete(self, keys: List[str]) -> int:
        """
        Batch delete keys (implemented as writing empty bytes) using Python SDK

        Args:
            keys: List of keys to delete

        Returns:
            Number of keys successfully deleted
        """
        if not keys:
            return 0

        try:
            # Warning: batch_delete during batch mode may cause conflicts
            if self._batch_mode:
                logger.warning(
                    f"⚠️  batch_delete() called during batch mode for {len(keys)} keys. "
                    "This will create a separate upload operation and may conflict with batch commit."
                )

            # Build KV payload with multiple empty values
            builder = StreamDataBuilder()
            for key in keys:
                key_bytes = key.encode('utf-8')
                builder.set(
                    stream_id=self.stream_id,
                    key=key_bytes,
                    data=b''  # Empty bytes for deletion
                )

            # Upload to 0G-Storage
            tx, root = await self._upload_builder(builder)
            logger.debug(f"✅ Batch delete {len(keys)} keys, tx={tx}")
            return len(keys)

        except Exception as e:
            logger.error(f"❌ Failed to batch delete {len(keys)} keys: {e}")
            return 0


    async def begin_batch(self) -> None:
        """
        Begin batch mode - accumulate write operations without committing

        Creates a new StreamDataBuilder to stage multiple put() operations.
        Call commit_batch() to upload all staged operations at once.

        This avoids parallel write conflicts in 0G-Storage.

        Note: Uses lock to prevent concurrent batch operations from different requests.
        If another request is already in batch mode, this will wait.
        """
        # Acquire lock to prevent concurrent batch operations
        await self._batch_lock.acquire()

        try:
            if self._batch_mode:
                logger.warning("⚠️  Batch mode already active (should not happen with lock)")

            # Initialize builder and operations first (may throw)
            batch_builder = StreamDataBuilder()
            batch_operations = []

            # Only set state after successful initialization
            self._batch_mode = True
            self._batch_builder = batch_builder
            self._batch_operations = batch_operations
            logger.debug("📦 Batch mode started (lock acquired)")
        except Exception as e:
            # Release lock and reset state if initialization fails
            self._batch_mode = False
            self._batch_builder = None
            self._batch_operations = []
            self._batch_lock.release()
            logger.error(f"❌ Failed to begin batch: {e}")
            raise


    async def commit_batch(self) -> bool:
        """
        Commit all staged write operations from batch mode

        Builds and uploads all staged put() operations as a single transaction.
        Releases the batch lock after commit (success or failure).

        Returns:
            True if commit successful
        """
        success = True

        try:
            if not self._batch_mode:
                logger.warning("⚠️  Batch mode not active, nothing to commit")
                return True

            if not self._batch_operations:
                logger.debug("📦 Batch mode ending with no operations")
                return True

            try:
                # Upload all accumulated operations to 0G-Storage
                tx, root = await self._upload_builder(self._batch_builder)

                total_bytes = sum(size for _, size in self._batch_operations)
                logger.info(
                    f"✅ Batch commit successful: {len(self._batch_operations)} operations, "
                    f"{total_bytes} bytes total, tx={tx}, root={root}"
                )

            except Exception as e:
                logger.error(f"❌ Failed to commit batch: {e}")
                success = False

            return success

        finally:
            # Always reset batch state and release lock
            self._batch_mode = False
            self._batch_builder = None
            self._batch_operations = []

            if self._batch_lock.locked():
                self._batch_lock.release()
                logger.debug("📦 Batch lock released")


__all__ = ["ZeroGKVStorage"]
