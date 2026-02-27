"""Tool to clear all data in the currently configured KV storage

Reads KV_STORAGE_TYPE from .env to determine which backend to clear.
Uses iterate_all() to discover every key, then batch_delete() to remove them.
For 0G KV storage, commits and waits (flush) until all deletions are uploaded.

Usage:
    uv run python src/bootstrap.py demo/tools/clear_kv_data.py
"""

import asyncio
import sys
import os

BATCH_SIZE = 500


async def clear_kv_data(verbose: bool = True) -> dict:
    """
    Clear all entries from the currently active KV storage.

    Returns:
        dict with 'total' (keys found) and 'deleted' (keys deleted) counts
    """
    from core.di.utils import get_bean_by_type
    from infra_layer.adapters.out.persistence.kv_storage.kv_storage_interface import (
        KVStorageInterface,
    )

    kv = get_bean_by_type(KVStorageInterface)
    kv_type = type(kv).__name__

    if verbose:
        print(f"   KV storage backend: {kv_type}")
        print("   🔍 Scanning KV storage for all keys...")

    # Collect all keys via iterate_all
    keys = []
    async for key, _value in kv.iterate_all():
        keys.append(key)
        if verbose and len(keys) % 1000 == 0:
            print(f"   Scanned {len(keys)} keys so far...")

    if not keys:
        if verbose:
            print("   ✅ KV storage is already empty")
        return {"total": 0, "deleted": 0}

    if verbose:
        print(f"   Found {len(keys)} keys total")
        print(f"   🗑️  Deleting in batches of {BATCH_SIZE}...")

    # Batch delete all keys
    deleted = 0
    for i in range(0, len(keys), BATCH_SIZE):
        batch = keys[i : i + BATCH_SIZE]
        n = await kv.batch_delete(batch)
        deleted += n
        if verbose:
            batch_num = i // BATCH_SIZE + 1
            total_batches = (len(keys) + BATCH_SIZE - 1) // BATCH_SIZE
            print(f"   Batch {batch_num}/{total_batches}: deleted {n}/{len(batch)} keys")

    # For 0G KV storage:
    # commit() is non-blocking — it only enqueues the batch for the background upload worker.
    # flush() blocks until the worker actually finishes uploading to the chain.
    # Without flush(), the process may exit before the upload completes (daemon thread killed).
    try:
        from infra_layer.adapters.out.persistence.kv_storage.zerog_kv_storage import (
            ZeroGKVStorage,
        )
        if isinstance(kv, ZeroGKVStorage):
            if verbose:
                print("   🔄 0G KV: committing staged deletions...")
            kv._cached.commit()
            if verbose:
                print("   ⏳ 0G KV: waiting for upload to complete (flush)...")
            kv._cached.flush()  # blocks until background worker finishes the upload
            if verbose:
                print("   ✅ 0G KV: all deletions uploaded to chain")
    except ImportError:
        pass

    if verbose:
        print(f"   ✅ Deleted {deleted}/{len(keys)} keys from KV storage")

    return {"total": len(keys), "deleted": deleted}


async def main():
    print("=" * 70)
    print("🗑️  Clear KV Storage Data Tool")
    print("=" * 70)

    # setup_project_context() is already called by bootstrap.py before running this script.
    # Only call it when running standalone (bootstrap sets BOOTSTRAP_MODE=true).
    is_bootstrap = os.getenv("BOOTSTRAP_MODE", "false").lower() == "true"
    if not is_bootstrap:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))
        from bootstrap import setup_project_context
        await setup_project_context()

    kv_type = os.getenv("KV_STORAGE_TYPE", "inmemory")
    print(f"\nKV_STORAGE_TYPE = {kv_type}")
    print()

    print("   📦 Clearing KV storage...")
    stats = await clear_kv_data(verbose=True)

    print()
    print("📊 Result:")
    print(f"   Keys found   : {stats['total']}")
    print(f"   Keys deleted : {stats['deleted']}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
