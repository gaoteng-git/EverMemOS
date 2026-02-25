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
        pass

    async def get(self, key: str) -> Optional[str]:
        pass

    async def put(self, key: str, value: str) -> bool:
        pass

    async def delete(self, key: str) -> bool:
        pass

    async def batch_get(self, keys: List[str]) -> Dict[str, str]:
        pass

    async def batch_delete(self, keys: List[str]) -> int:
        pass


__all__ = ["ZeroGKVStorage"]
