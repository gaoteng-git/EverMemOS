"""
0G-Storage based KV-Storage implementation

Uses 0g-storage Python SDK (CachedKvClient) for storage operations.
All values are UTF-8 encoded as bytes.

Key Format: {collection_name}:{document_id}
Example: "episodic_memories:6979da5797f9041fc0aa063f"

Environment Variables Required:
- ZEROG_WALLET_KEY: Wallet private key (IMPORTANT: Keep secure!)

Concurrency Model:
- Single CachedKvClient shared across all coroutines/threads.
- One threading.Lock (_lock) serializes staged-write operations:
    cached.set (put/delete) and _pending_count updates.
- A dedicated background daemon thread (_commit_thread) wakes up every
  COMMIT_INTERVAL seconds. If _pending_count > 0, it calls cached.commit()
  (non-blocking: actual upload happens inside the SDK) and resets the counter;
  otherwise it skips the interval entirely.
- Lock is NOT held during commit(); it is only held during cached.set() calls.
"""

import asyncio
import os
import threading
from typing import Optional, Dict, List, Tuple, AsyncIterator

from core.observation.logger import get_logger
from core.di.decorators import component
from .kv_storage_interface import KVStorageInterface

from zg_storage import CachedKvClient, EvmClient, UploadOption

logger = get_logger(__name__)

COMMIT_INTERVAL = 20  # seconds between commit attempts


@component("zerog_kv_storage")
class ZeroGKVStorage(KVStorageInterface):
    """
    0G-Storage based KV-Storage implementation using CachedKvClient.

    put/delete: call cached.set() to stage the op (fast, in-memory).
    commit: a dedicated background thread wakes every COMMIT_INTERVAL seconds
            and calls cached.commit() only if there are pending staged ops.
    get: cached.get_bytes() reads from local cache or the KV node.
    """

    def __init__(
        self,
        kv_url: str,                    # KV node URL for reads/writes
        stream_id: str,                 # Unified stream ID for all collections
        rpc_url: str,                   # "https://evmrpc-testnet.0g.ai"
        indexer_url: str,               # Indexer URL for uploads
        flow_address: str,              # Flow contract address
        max_queue_size: int = 100,      # Internal write queue size
        max_cache_entries: int = 10000, # Local read cache size
    ):
        self.stream_id = stream_id

        wallet_private_key = os.getenv('ZEROG_WALLET_KEY')
        if not wallet_private_key:
            raise ValueError("ZEROG_WALLET_KEY environment variable is required")

        evm = EvmClient(
            rpc_url=rpc_url,
            private_key=wallet_private_key,
        )

        self._cached = CachedKvClient(
            kv_url=kv_url,
            indexer_url=indexer_url,
            evm_client=evm,
            flow_address=flow_address,
            max_queue_size=max_queue_size,
            max_cache_entries=max_cache_entries,
            upload_option=UploadOption(skip_tx=False),
        )

        # Lock protecting cached.set() calls and _pending_count.
        self._lock = threading.Lock()

        # Number of ops staged since the last commit. Protected by _lock.
        self._pending_count: int = 0

        # Background commit thread
        self._stop_event = threading.Event()
        self._commit_thread = threading.Thread(
            target=self._commit_loop,
            name="zerog_commit",
            daemon=True,
        )
        self._commit_thread.start()

        logger.info(
            f"✅ ZeroGKVStorage initialized: stream_id={stream_id}, "
            f"kv_url={kv_url}, indexer_url={indexer_url}, "
            f"commit_interval={COMMIT_INTERVAL}s"
        )

    # -------------------------------------------------------------------------
    # Internal: time-based commit loop
    # -------------------------------------------------------------------------

    def _commit_loop(self) -> None:
        """
        Dedicated background thread.
        Wakes up every COMMIT_INTERVAL seconds.
        If _pending_count > 0, calls cached.commit() (non-blocking) and resets
        the counter. If _pending_count == 0, skips the interval silently.
        """
        while not self._stop_event.wait(COMMIT_INTERVAL):
            with self._lock:
                if self._pending_count == 0:
                    continue
                pending = self._pending_count
                self._pending_count = 0

            try:
                self._cached.commit()
                logger.info(f"✅ Commit triggered ({pending} pending ops)")
            except Exception as e:
                logger.error(f"❌ Commit failed: {e}", exc_info=True)

    # -------------------------------------------------------------------------
    # Internal: stage a set/delete operation
    # -------------------------------------------------------------------------

    def _stage_operation(self, key: str, value_bytes: bytes) -> bool:
        """
        Call cached.set() under lock, then increment _pending_count.
        The commit thread will flush to the chain on the next interval.
        """
        key_bytes = key.encode('utf-8')
        with self._lock:
            self._cached.set(self.stream_id, key_bytes, value_bytes)
            self._pending_count += 1
        return True

    # -------------------------------------------------------------------------
    # KVStorageInterface implementation
    # -------------------------------------------------------------------------

    async def get(self, key: str) -> Optional[str]:
        try:
            key_bytes = key.encode('utf-8')
            loop = asyncio.get_event_loop()
            value_bytes = await loop.run_in_executor(
                None, self._cached.get_bytes, self.stream_id, key_bytes
            )
            if not value_bytes:
                return None
            return value_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"❌ Failed to get key {key}: {e}")
            return None

    async def put(self, key: str, value: str) -> bool:
        """Stage a put operation. Commit happens in the background thread."""
        try:
            return self._stage_operation(key, value.encode('utf-8'))
        except Exception as e:
            logger.error(f"❌ Failed to put key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Stage a delete operation (empty bytes). Commit happens in the background thread."""
        try:
            return self._stage_operation(key, b'')
        except Exception as e:
            logger.error(f"❌ Failed to delete key {key}: {e}")
            return False

    async def batch_get(self, keys: List[str]) -> Dict[str, str]:
        if not keys:
            return {}

        result = {}
        try:
            loop = asyncio.get_event_loop()
            for key in keys:
                key_bytes = key.encode('utf-8')
                value_bytes = await loop.run_in_executor(
                    None, self._cached.get_bytes, self.stream_id, key_bytes
                )
                if value_bytes:
                    result[key] = value_bytes.decode('utf-8')

            logger.debug(f"✅ Batch get {len(result)}/{len(keys)} keys")
            return result

        except Exception as e:
            logger.error(f"❌ Failed to batch get {len(keys)} keys: {e}")
            return {}

    async def batch_delete(self, keys: List[str]) -> int:
        """Stage delete for each key. Commit happens in the background thread."""
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

    async def iterate_all(self) -> AsyncIterator[Tuple[str, str]]:
        """
        Iterate all key-value pairs using CachedKvClient's iterator.
        Empty/deleted entries (empty bytes) are skipped.
        """
        try:
            loop = asyncio.get_event_loop()

            iterator = await loop.run_in_executor(
                None, self._cached._kv_client.new_iterator, "0x" + self.stream_id
            )
            await loop.run_in_executor(None, iterator.seek_to_first)

            total_count = 0
            skipped_count = 0

            while True:
                valid = await loop.run_in_executor(None, iterator.valid)
                if not valid:
                    break

                key_bytes = await loop.run_in_executor(None, lambda: iterator.key)
                data_bytes = await loop.run_in_executor(None, lambda: iterator.data)

                key = key_bytes.decode('utf-8')

                if data_bytes and len(data_bytes) > 0:
                    value = data_bytes.decode('utf-8')
                    total_count += 1
                    yield (key, value)
                else:
                    skipped_count += 1

                await loop.run_in_executor(None, iterator.next)

                if (total_count + skipped_count) % 1000 == 0 and (total_count + skipped_count) > 0:
                    logger.debug(
                        f"📊 ZeroG iterate progress: {total_count} yielded, "
                        f"{skipped_count} skipped (empty/deleted)"
                    )

            logger.info(
                f"✅ ZeroG iterate_all completed: {total_count} yielded, "
                f"{skipped_count} skipped"
            )

        except Exception as e:
            logger.error(f"❌ ZeroG iterate_all failed: {e}", exc_info=True)
            raise

    def close(self) -> None:
        """
        Stop the commit thread, flush any remaining pending ops, then
        release CachedKvClient resources.
        """
        self._stop_event.set()
        self._commit_thread.join(timeout=5)

        # CachedKvClient.close() will itself commit any remaining pending writes
        # and wait for all queued uploads to finish before shutting down the worker.
        try:
            self._cached.close()
            logger.info("✅ ZeroGKVStorage closed")
        except Exception as e:
            logger.error(f"❌ Failed to close CachedKvClient: {e}")


__all__ = ["ZeroGKVStorage"]
