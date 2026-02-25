"""
0G-Storage based KV-Storage implementation

Uses 0g-storage Python SDK for storage operations.
All values are UTF-8 encoded as bytes.

Key Format: {collection_name}:{document_id}
Example: "episodic_memories:6979da5797f9041fc0aa063f"

Environment Variables Required:
- ZEROG_WALLET_KEY: Wallet private key (IMPORTANT: Keep secure!)

Concurrency Model:
- Single shared StreamDataBuilder and uploader across all coroutines/threads
- One threading.Lock (_lock) serializes all builder operations:
    builder.set (put/delete), builder.get (get), builder.build + stream_ids (commit)
- _commit_sync runs exclusively in a single-thread executor: never parallel
- Lock is held briefly for set/get; also for build+clear in commit (upload is outside lock)
- After COMMIT_THRESHOLD pending ops, _commit is submitted to the background thread
"""

import os
import threading
import concurrent.futures
from typing import Optional, Dict, List

from core.observation.logger import get_logger
from core.di.decorators import component
from .kv_storage_interface import KVStorageInterface

from zg_storage import EvmClient
from zg_storage.core.data import BytesDataSource
from zg_storage.indexer import IndexerClient
from zg_storage.kv import StreamDataBuilder
from zg_storage.kv.types import create_tags
from zg_storage.transfer import NodeUploader, NodeUploaderConfig, UploadOption

logger = get_logger(__name__)

COMMIT_THRESHOLD = 100  # Trigger _commit after this many staged operations


@component("zerog_kv_storage")
class ZeroGKVStorage(KVStorageInterface):
    """
    0G-Storage based KV-Storage implementation.

    All put/delete operations are staged into a shared StreamDataBuilder.
    When COMMIT_THRESHOLD operations accumulate, _commit is submitted to a
    single-thread background executor, which serializes all uploads.
    """

    def __init__(
        self,
        nodes: str,                    # "http://35.236.80.213:5678,http://34.102.76.235:5678"
        stream_id: str,                # Unified stream ID for all collections
        rpc_url: str,                  # "https://evmrpc-testnet.0g.ai"
        read_node: str,                # "http://34.31.1.26:6789" (kept for future read use)
        timeout: int = 30,             # Request timeout in seconds
        max_retries: int = 3,          # Max retry attempts
        use_indexer: bool = True,      # Use IndexerClient (True) or NodeUploader (False)
        indexer_url: Optional[str] = None,   # Indexer URL (required if use_indexer=True)
        flow_address: Optional[str] = None,  # Flow contract address (required if use_indexer=True)
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

        wallet_private_key = os.getenv('ZEROG_WALLET_KEY')
        if not wallet_private_key:
            raise ValueError("ZEROG_WALLET_KEY environment variable is required")

        # EVM client
        self._evm_client = EvmClient(
            rpc_url=self.rpc_url,
            private_key=wallet_private_key,
        )

        # Uploader: IndexerClient or NodeUploader
        if self.use_indexer:
            self._uploader = IndexerClient(
                self.indexer_url,
                evm_client=self._evm_client,
                flow_address=self.flow_address,
            )
            logger.info(f"✅ Using IndexerClient: {self.indexer_url}")
        else:
            cfg = NodeUploaderConfig(
                nodes=self.nodes,
                evm_client=self._evm_client,
                flow_address=self.flow_address,
                rpc_timeout=float(self.timeout),
            )
            self._uploader = NodeUploader.from_config(cfg)
            logger.info(f"✅ Using NodeUploader: {self.nodes[0]}...")

        # Shared StreamDataBuilder — one instance, shared by all coroutines/threads
        self._builder = StreamDataBuilder()

        # One lock to protect ALL builder operations:
        #   builder.set   (in _stage_operation)
        #   builder.get   (in get / batch_get)       -- pseudocode, see note below
        #   builder.build + builder.stream_ids        (in _commit_sync)
        #   builder.clear                             (in _commit_sync, TODO)
        #   _pending_count read/write
        self._lock = threading.Lock()

        # Number of staged (not yet committed) operations, protected by _lock
        self._pending_count = 0

        # Single-thread executor: _commit_sync is always submitted here.
        # max_workers=1 guarantees serial execution — _commit never runs in parallel.
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="zerog_commit",
        )

        logger.info(
            f"✅ ZeroGKVStorage initialized: stream_id={stream_id}, "
            f"use_indexer={use_indexer}, timeout={timeout}s"
        )

    # -------------------------------------------------------------------------
    # Internal: commit
    # -------------------------------------------------------------------------

    def _commit_sync(self) -> None:
        """
        Build the current builder snapshot and upload to 0G-Storage.

        Runs exclusively in self._executor (single-thread), so it is NEVER
        called concurrently. The lock is held only for the brief build+clear
        phase; the actual network upload happens outside the lock.
        """
        try:
            # --- critical section: snapshot + clear ---
            with self._lock:
                stream_data = self._builder.build(sorted_items=True)
                tags = create_tags(self._builder.stream_ids(), sorted_ids=True)
                # TODO: self._builder.clear()  # clear staged ops after snapshot

            # --- upload: outside lock so other coroutines can keep staging ---
            payload = stream_data.encode()
            opt = UploadOption(tags=tags)
            tx, root = self._uploader.upload(
                file_path=BytesDataSource(payload),
                tags=tags,
                option=opt,
            )
            logger.info(f"✅ Commit successful: tx={tx}, root={root}")

        except Exception as e:
            logger.error(f"❌ Commit failed: {e}", exc_info=True)

    # -------------------------------------------------------------------------
    # Internal: stage a set/delete operation
    # -------------------------------------------------------------------------

    def _stage_operation(self, key: str, value_bytes: bytes) -> bool:
        """
        Call builder.set under lock, increment pending count, and submit
        _commit_sync to the executor when COMMIT_THRESHOLD is reached.

        Returns True if the operation was staged successfully.
        """
        key_bytes = key.encode('utf-8')

        with self._lock:
            self._builder.set(
                stream_id=self.stream_id,
                key=key_bytes,
                data=value_bytes,
            )
            self._pending_count += 1
            should_commit = self._pending_count >= COMMIT_THRESHOLD
            if should_commit:
                # Reset counter before releasing lock so only one caller
                # at the threshold triggers a commit.
                self._pending_count = 0

        if should_commit:
            self._executor.submit(self._commit_sync)

        return True

    # -------------------------------------------------------------------------
    # KVStorageInterface implementation
    # -------------------------------------------------------------------------

    async def get(self, key: str) -> Optional[str]:
        """
        Get value by key from the local builder state (staged, not yet uploaded).

        NOTE: builder.get is pseudocode — the actual SDK method name may differ.
        This reads uncommitted (locally staged) writes only.
        """
        try:
            key_bytes = key.encode('utf-8')

            with self._lock:
                # PSEUDOCODE: builder.get does not exist in the current SDK.
                # Replace with the correct SDK call when available.
                value_bytes = self._builder.get(  # type: ignore[attr-defined]
                    stream_id=self.stream_id,
                    key=key_bytes,
                )

            if value_bytes is None or len(value_bytes) == 0:
                return None

            return value_bytes.decode('utf-8')

        except Exception as e:
            logger.error(f"❌ Failed to get key {key}: {e}")
            return None

    async def put(self, key: str, value: str) -> bool:
        """
        Stage a put operation (builder.set).
        Triggers _commit when COMMIT_THRESHOLD ops accumulate.
        """
        try:
            return self._stage_operation(key, value.encode('utf-8'))
        except Exception as e:
            logger.error(f"❌ Failed to put key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        Stage a delete operation (builder.set with empty bytes).
        Triggers _commit when COMMIT_THRESHOLD ops accumulate.
        """
        try:
            return self._stage_operation(key, b'')
        except Exception as e:
            logger.error(f"❌ Failed to delete key {key}: {e}")
            return False

    async def batch_get(self, keys: List[str]) -> Dict[str, str]:
        """
        Batch get values from local builder state.

        NOTE: builder.get is pseudocode — see get() for details.
        """
        if not keys:
            return {}

        result = {}
        try:
            for key in keys:
                key_bytes = key.encode('utf-8')

                with self._lock:
                    # PSEUDOCODE: builder.get does not exist in the current SDK.
                    value_bytes = self._builder.get(  # type: ignore[attr-defined]
                        stream_id=self.stream_id,
                        key=key_bytes,
                    )

                if value_bytes and len(value_bytes) > 0:
                    result[key] = value_bytes.decode('utf-8')

            logger.debug(f"✅ Batch get {len(result)}/{len(keys)} keys")
            return result

        except Exception as e:
            logger.error(f"❌ Failed to batch get {len(keys)} keys: {e}")
            return {}

    async def batch_delete(self, keys: List[str]) -> int:
        """
        Stage delete (empty bytes) for each key.
        May trigger one or more _commit calls if COMMIT_THRESHOLD is crossed.
        """
        if not keys:
            return 0

        deleted = 0
        for key in keys:
            try:
                if self._stage_operation(key, b''):
                    deleted += 1
            except Exception as e:
                logger.error(f"❌ Failed to stage delete for key {key}: {e}")

        return deleted


__all__ = ["ZeroGKVStorage"]
