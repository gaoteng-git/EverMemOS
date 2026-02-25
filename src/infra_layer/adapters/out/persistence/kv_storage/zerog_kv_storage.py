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
- At most ONE _commit_sync task ever lives in the executor at a time (_commit_running flag).
  No queue of pending commits: if a commit is already running, stage ops accumulate and
  will be picked up by the drain loop inside the running commit.
- _commit_sync drain loop: after each upload, if _pending_count >= COMMIT_THRESHOLD,
  immediately commit again without returning to the executor queue.
- Lock is held briefly for set/get and for build+clear; upload happens outside the lock.
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
    When COMMIT_THRESHOLD operations accumulate, a single _commit_sync task is
    submitted to a single-thread executor. That task loops internally:
    after each upload it rechecks _pending_count and commits again if still
    >= COMMIT_THRESHOLD, so no commits ever queue up behind each other.
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

        # One lock protecting ALL builder operations and the two fields below:
        #   builder.set   (_stage_operation)
        #   builder.get   (get / batch_get)        -- pseudocode, see note
        #   builder.build + builder.stream_ids + builder.clear  (_commit_sync)
        #   _pending_count
        #   _commit_running
        self._lock = threading.Lock()

        # Ops staged since the last commit snapshot, protected by _lock.
        self._pending_count: int = 0

        # True while _commit_sync is running in the executor, protected by _lock.
        # Prevents multiple commits from queuing up: at most one commit task lives
        # in the executor at any time.
        self._commit_running: bool = False

        # Single-thread executor — _commit_sync always runs on this one thread.
        # max_workers=1 is a safety net; _commit_running already prevents queuing.
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="zerog_commit",
        )

        logger.info(
            f"✅ ZeroGKVStorage initialized: stream_id={stream_id}, "
            f"use_indexer={use_indexer}, timeout={timeout}s"
        )

    # -------------------------------------------------------------------------
    # Internal: commit (drain loop)
    # -------------------------------------------------------------------------

    def _commit_sync(self) -> None:
        """
        Take a snapshot of the builder, upload to 0G-Storage, then loop:
        if _pending_count has reached COMMIT_THRESHOLD again (ops accumulated
        during the upload), commit immediately without re-queuing.

        Runs exclusively in self._executor (single thread). _commit_running
        ensures only one instance of this method is ever active.
        """
        while True:
            # --- Step 1: take snapshot under lock ---
            try:
                with self._lock:
                    stream_data = self._builder.build(sorted_items=True)
                    tags = create_tags(self._builder.stream_ids(), sorted_ids=True)
                    # TODO: self._builder.clear()  # clear staged ops after snapshot
                    committed_count = self._pending_count
                    self._pending_count = 0
            except Exception as e:
                logger.error(f"❌ Commit snapshot failed: {e}", exc_info=True)
                with self._lock:
                    self._commit_running = False
                return

            # --- Step 2: upload outside lock ---
            try:
                payload = stream_data.encode()
                opt = UploadOption(tags=tags)
                tx, root = self._uploader.upload(
                    file_path=BytesDataSource(payload),
                    tags=tags,
                    option=opt,
                )
                logger.info(f"✅ Commit ({committed_count} ops): tx={tx}, root={root}")
            except Exception as e:
                logger.error(f"❌ Commit upload failed: {e}", exc_info=True)
                with self._lock:
                    self._commit_running = False
                return

            # --- Step 3: drain loop check ---
            # During the upload, new ops may have accumulated. If enough have
            # built up, commit again immediately rather than waiting for the
            # next threshold crossing in _stage_operation.
            with self._lock:
                if self._pending_count < COMMIT_THRESHOLD:
                    # Not enough for another commit; release the running flag
                    # so the next threshold crossing in _stage_operation can
                    # re-submit.
                    self._commit_running = False
                    return
                # else: fall through and loop — _commit_running stays True

    # -------------------------------------------------------------------------
    # Internal: stage a set/delete operation
    # -------------------------------------------------------------------------

    def _stage_operation(self, key: str, value_bytes: bytes) -> bool:
        """
        Call builder.set under lock, then submit _commit_sync if the threshold
        is reached AND no commit is already running.
        """
        key_bytes = key.encode('utf-8')
        should_submit = False

        with self._lock:
            self._builder.set(
                stream_id=self.stream_id,
                key=key_bytes,
                data=value_bytes,
            )
            self._pending_count += 1

            # Submit a new commit only when threshold is crossed AND no commit
            # is currently running. If a commit is running, the drain loop
            # will pick up these ops after the current upload finishes.
            if self._pending_count >= COMMIT_THRESHOLD and not self._commit_running:
                self._commit_running = True
                should_submit = True

        if should_submit:
            try:
                self._executor.submit(self._commit_sync)
            except Exception as e:
                logger.error(f"❌ Failed to submit commit task: {e}", exc_info=True)
                with self._lock:
                    self._commit_running = False

        return True

    # -------------------------------------------------------------------------
    # KVStorageInterface implementation
    # -------------------------------------------------------------------------

    async def get(self, key: str) -> Optional[str]:
        """
        Get value by key from the local builder state (staged, not yet uploaded).

        NOTE: builder.get is pseudocode — StreamDataBuilder does not expose a
        get() method in the current SDK. Replace with the correct call when available.
        """
        try:
            key_bytes = key.encode('utf-8')

            with self._lock:
                # PSEUDOCODE: builder.get does not exist in the current SDK.
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
        Triggers _commit when COMMIT_THRESHOLD ops accumulate and no commit is running.
        """
        try:
            return self._stage_operation(key, value.encode('utf-8'))
        except Exception as e:
            logger.error(f"❌ Failed to put key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        Stage a delete operation (builder.set with empty bytes).
        Triggers _commit when COMMIT_THRESHOLD ops accumulate and no commit is running.
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
        May trigger a _commit if COMMIT_THRESHOLD is crossed and no commit is running.
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
