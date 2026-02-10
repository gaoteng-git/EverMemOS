"""
0G-Storage based KV-Storage implementation

Uses 0g-storage Python SDK for storage operations.
All values are Base64 encoded to avoid \\n and , issues.

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
from .encoding_utils import (
    encode_value_for_zerog,
    decode_value_from_zerog,
    decode_values_batch
)

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
    All values are Base64 encoded to avoid \\n and , issues.

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
        indexer_url: str = "https://indexer-storage-testnet-turbo.0g.ai",  # Indexer URL
        flow_address: str = "0x22E03a6A89B950F1c82ec5e74F8eCa321a105296"   # Flow contract address
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

        logger.info(
            f"✅ ZeroGKVStorage initialized with Python SDK\n"
            f"   Stream ID: {stream_id}\n"
            f"   RPC URL: {rpc_url}\n"
            f"   Read Node: {read_node}\n"
            f"   Timeout: {timeout}s"
        )


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

            # Decode bytes to string (already Base64 encoded)
            encoded_value = value_bytes.decode('utf-8')

            # Base64 decode to get original JSON
            json_value = decode_value_from_zerog(encoded_value)
            logger.debug(f"✅ Get key: {key} ({len(json_value)} bytes)")
            return json_value

        except Exception as e:
            logger.error(f"❌ Failed to get key {key}: {e}")
            return None


    async def put(self, key: str, value: str) -> bool:
        """
        Store key-value pair using Python SDK

        Args:
            key: Full key including collection prefix (e.g., "episodic_memories:123")
            value: JSON string to store

        Returns:
            True if successful
        """
        try:
            # Base64 encode value
            encoded_value = encode_value_for_zerog(value)

            # Convert to bytes
            key_bytes = key.encode('utf-8')
            value_bytes = encoded_value.encode('utf-8')

            # Build KV payload using StreamDataBuilder
            builder = StreamDataBuilder()
            builder.set(
                stream_id=self.stream_id,
                key=key_bytes,
                data=value_bytes
            )
            stream_data = builder.build(sorted_items=True)
            payload = stream_data.encode()
            tags = create_tags(builder.stream_ids(), sorted_ids=True)

            # Upload option
            opt = UploadOption(tags=tags)

            # Upload using SDK in thread pool
            loop = asyncio.get_event_loop()
            tx, root = await loop.run_in_executor(
                None,
                lambda: self.uploader.upload(
                    file_path=BytesDataSource(payload),
                    tags=tags,
                    option=opt
                )
            )

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
            stream_data = builder.build(sorted_items=True)
            payload = stream_data.encode()
            tags = create_tags(builder.stream_ids(), sorted_ids=True)

            # Upload option
            opt = UploadOption(tags=tags)

            # Upload using SDK in thread pool
            loop = asyncio.get_event_loop()
            tx, root = await loop.run_in_executor(
                None,
                lambda: self.uploader.upload(
                    file_path=BytesDataSource(payload),
                    tags=tags,
                    option=opt
                )
            )

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
            # and Base64 decode values
            result = {}
            for key_bytes, value_bytes in data.items():
                if value_bytes and len(value_bytes) > 0:
                    key_str = key_bytes.decode('utf-8')
                    encoded_value = value_bytes.decode('utf-8')

                    # Base64 decode to get original JSON
                    try:
                        json_value = decode_value_from_zerog(encoded_value)
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
            # Build KV payload with multiple empty values
            builder = StreamDataBuilder()
            for key in keys:
                key_bytes = key.encode('utf-8')
                builder.set(
                    stream_id=self.stream_id,
                    key=key_bytes,
                    data=b''  # Empty bytes for deletion
                )

            stream_data = builder.build(sorted_items=True)
            payload = stream_data.encode()
            tags = create_tags(builder.stream_ids(), sorted_ids=True)

            # Upload option
            opt = UploadOption(tags=tags)

            # Upload using SDK in thread pool
            loop = asyncio.get_event_loop()
            tx, root = await loop.run_in_executor(
                None,
                lambda: self.uploader.upload(
                    file_path=BytesDataSource(payload),
                    tags=tags,
                    option=opt
                )
            )

            logger.debug(f"✅ Batch delete {len(keys)} keys, tx={tx}")
            return len(keys)

        except Exception as e:
            logger.error(f"❌ Failed to batch delete {len(keys)} keys: {e}")
            return 0


__all__ = ["ZeroGKVStorage"]
