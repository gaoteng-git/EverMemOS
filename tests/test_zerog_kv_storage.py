#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Integration Tests for ZeroGKVStorage

Tests real 0G-Storage operations with actual network calls.
Requires valid 0G-Storage configuration in .env file.

⚠️  WARNING: These are INTEGRATION tests, not unit tests!
- They make real network calls to 0G-Storage
- They will be slower than unit tests (network latency)
- They require valid credentials in .env file
- They will write real data to 0G-Storage testnet
"""

import asyncio
import os
import pytest
import pytest_asyncio
import uuid
import time
from typing import Dict, List
from dotenv import load_dotenv

# Mark all test functions in this module as asyncio tests
pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="session", autouse=True)
def load_env():
    """Load environment variables from .env file"""
    # Try multiple .env file locations
    env_files = [
        ".env",
        ".env.zerog",
        os.path.join(os.path.dirname(__file__), "..", ".env"),
    ]

    for env_file in env_files:
        if os.path.exists(env_file):
            load_dotenv(env_file)
            print(f"✅ Loaded environment from: {env_file}")
            break
    else:
        print("⚠️  Warning: No .env file found, using environment variables")


@pytest_asyncio.fixture
async def zerog_storage():
    """Create real ZeroGKVStorage instance with config from .env"""
    from infra_layer.adapters.out.persistence.kv_storage.zerog_kv_storage import ZeroGKVStorage

    # Read configuration from environment variables
    nodes = 'http://35.236.80.213:5678,http://34.102.76.235:5678'
    stream_id = '0000000000000000000000000000000000000000000000000000000000006e3d'
    rpc_url = 'https://evmrpc-testnet.0g.ai'
    read_node = 'http://127.0.0.1:6789'
    timeout = 30
    max_retries = 3

    # Indexer configuration (if available)
    use_indexer = True
    indexer_url = 'https://indexer-storage-testnet-turbo.0g.ai'
    flow_address = '0x22E03a6A89B950F1c82ec5e74F8eCa321a105296'

    # Check for required ZEROG_WALLET_KEY
    if not os.getenv('ZEROG_WALLET_KEY'):
        pytest.skip("ZEROG_WALLET_KEY not found in environment. Set it in .env file to run integration tests.")

    print(f"\n🔧 ZeroGKVStorage Configuration:")
    print(f"   Stream ID: {stream_id}")
    print(f"   RPC URL: {rpc_url}")
    print(f"   Read Node: {read_node}")
    print(f"   Use Indexer: {use_indexer}")
    if use_indexer:
        print(f"   Indexer URL: {indexer_url}")

    # Create real ZeroGKVStorage instance
    storage = ZeroGKVStorage(
        nodes=nodes,
        stream_id=stream_id,
        rpc_url=rpc_url,
        read_node=read_node,
        timeout=timeout,
        max_retries=max_retries,
        use_indexer=use_indexer,
        indexer_url=indexer_url if use_indexer else None,
        flow_address=flow_address if use_indexer else None
    )

    yield storage

    # Cleanup: clear any batch state
    storage._ctx_batch_builder.set(None)
    storage._ctx_batch_operations.set(None)


def generate_test_key(prefix: str = "test") -> str:
    """Generate a unique test key"""
    return f"test_collection:{prefix}_{uuid.uuid4().hex[:8]}"


async def wait_for_data_sync(zerog_storage, key: str, expected_value: str = None,
                              max_retries: int = 10, retry_delay: float = 1.0,
                              initial_delay: float = 5.0) -> str:
    """
    Wait for data to sync to read nodes after write

    Strategy:
    1. Wait 5 seconds initially
    2. Try reading every 1 second, up to 10 times
    3. Total timeout: 5 + 10 = 15 seconds

    Args:
        zerog_storage: ZeroGKVStorage instance
        key: Key to read
        expected_value: Expected value (optional, for verification)
        max_retries: Maximum number of read attempts (default: 10)
        retry_delay: Delay between retries in seconds (default: 1.0)
        initial_delay: Initial wait time before first read attempt (default: 5.0)

    Returns:
        Retrieved value

    Raises:
        AssertionError if data not available after 15 seconds total
    """
    # Wait initially before first read attempt (data needs time to propagate)
    await asyncio.sleep(initial_delay)

    for attempt in range(max_retries):
        retrieved = await zerog_storage.get(key)

        if retrieved is not None:
            if expected_value is None or retrieved == expected_value:
                total_time = initial_delay + (attempt * retry_delay)
                print(f"   ✅ Data synced after {total_time:.1f}s ({attempt + 1} read attempts)")
                return retrieved

        if attempt < max_retries - 1:
            await asyncio.sleep(retry_delay)

    # Timeout after 15 seconds
    total_wait = initial_delay + (max_retries * retry_delay)
    raise AssertionError(
        f"❌ Timeout after {total_wait:.1f}s: key={key}, last value={retrieved}"
    )


async def wait_for_data_deletion(zerog_storage, key: str,
                                  max_retries: int = 10, retry_delay: float = 1.0,
                                  initial_delay: float = 5.0) -> None:
    """
    Wait for data deletion to sync to read nodes after delete

    Since 0G-KV-Storage delete is essentially writing empty value,
    it requires the same sync time as write operations.

    Strategy:
    1. Wait 5 seconds initially
    2. Try reading every 1 second, up to 10 times
    3. Total timeout: 5 + 10 = 15 seconds

    Args:
        zerog_storage: ZeroGKVStorage instance
        key: Key to verify deletion
        max_retries: Maximum number of read attempts (default: 10)
        retry_delay: Delay between retries in seconds (default: 1.0)
        initial_delay: Initial wait time before first read attempt (default: 5.0)

    Raises:
        AssertionError if key still exists after 15 seconds total
    """
    # Wait initially before first read attempt (delete needs time to propagate)
    await asyncio.sleep(initial_delay)

    for attempt in range(max_retries):
        retrieved = await zerog_storage.get(key)

        if retrieved is None:
            total_time = initial_delay + (attempt * retry_delay)
            print(f"   ✅ Deletion synced after {total_time:.1f}s ({attempt + 1} read attempts)")
            return

        if attempt < max_retries - 1:
            await asyncio.sleep(retry_delay)

    # Timeout after 15 seconds
    total_wait = initial_delay + (max_retries * retry_delay)
    raise AssertionError(
        f"❌ Timeout after {total_wait:.1f}s: key={key} still exists with value={retrieved}"
    )


class TestZeroGKVStorageInit:
    """Test initialization"""

    async def test_init_success(self, zerog_storage):
        """Test that ZeroGKVStorage initializes successfully"""
        assert zerog_storage is not None
        assert zerog_storage.stream_id is not None
        assert zerog_storage.kv_client is not None
        assert zerog_storage.uploader is not None


class TestNormalModeOperations:
    """Test normal mode operations (get, put, delete)"""

    async def test_put_and_get_success(self, zerog_storage):
        """Test put operation writes data and get reads it back"""
        key = generate_test_key("put_get")
        value = '{"name": "test", "value": 42, "timestamp": "2026-02-12"}'

        print(f"\n📝 Writing: {key} = {value}")

        # Write
        result = await zerog_storage.put(key, value)
        assert result is True, "Put operation failed"

        print(f"✅ Write successful, waiting for data sync...")

        # Read back and verify (with retry for data sync)
        retrieved = await wait_for_data_sync(zerog_storage, key, value)
        assert retrieved == value, f"Value mismatch: expected {value}, got {retrieved}"

        print(f"✅ Read successful, value matches!")

    async def test_get_non_existing_key(self, zerog_storage):
        """Test get operation for non-existing key returns None"""
        key = generate_test_key("non_existing")

        print(f"\n🔍 Reading non-existing key: {key}")

        result = await zerog_storage.get(key)
        assert result is None, f"Expected None for non-existing key, got {result}"

        print(f"✅ Correctly returned None for non-existing key")

    async def test_put_delete_get(self, zerog_storage):
        """Test full cycle: put -> verify -> delete -> verify deletion"""
        key = generate_test_key("delete_test")
        value = '{"data": "to_be_deleted"}'

        print(f"\n📝 Writing: {key} = {value}")

        # Write
        await zerog_storage.put(key, value)

        # Verify written (wait for sync)
        retrieved = await wait_for_data_sync(zerog_storage, key, value)
        assert retrieved == value, f"Write verification failed"

        print(f"✅ Write verified, now deleting...")

        # Delete
        result = await zerog_storage.delete(key)
        assert result is True, "Delete operation failed"

        print(f"✅ Delete successful, waiting for sync...")

        # Verify deleted (wait for delete to sync, same as write since delete = write empty value)
        await wait_for_data_deletion(zerog_storage, key)

        print(f"✅ Deletion verified!")

    async def test_put_overwrites_existing_value(self, zerog_storage):
        """Test that put overwrites existing value"""
        key = generate_test_key("overwrite")
        value1 = '{"version": 1}'
        value2 = '{"version": 2}'

        print(f"\n📝 Writing v1: {key} = {value1}")
        await zerog_storage.put(key, value1)
        await wait_for_data_sync(zerog_storage, key, value1)

        print(f"📝 Overwriting with v2: {value2}")
        await zerog_storage.put(key, value2)

        retrieved = await wait_for_data_sync(zerog_storage, key, value2)
        assert retrieved == value2, f"Expected {value2}, got {retrieved}"

        print(f"✅ Overwrite successful!")


class TestBatchOperations:
    """Test batch operations (batch_get, batch_delete)"""

    async def test_batch_get_multiple_keys(self, zerog_storage):
        """Test batch_get with multiple keys"""
        keys = [generate_test_key(f"batch_get_{i}") for i in range(3)]
        values = [f'{{"id": {i}}}' for i in range(3)]

        print(f"\n📝 Writing {len(keys)} keys for batch_get test...")

        # Write keys individually
        for key, value in zip(keys, values):
            await zerog_storage.put(key, value)
            print(f"   Written: {key}")

        print(f"✅ All keys written, waiting for sync...")

        # Wait for all keys to sync
        for key, value in zip(keys, values):
            await wait_for_data_sync(zerog_storage, key, value)

        print(f"✅ Data synced, now batch reading...")

        # Batch get
        result = await zerog_storage.batch_get(keys)

        assert len(result) == len(keys), f"Expected {len(keys)} results, got {len(result)}"

        for key, expected_value in zip(keys, values):
            assert key in result, f"Key {key} not in batch_get result"
            assert result[key] == expected_value, f"Value mismatch for {key}"

        print(f"✅ Batch get successful, all values match!")

    async def test_batch_delete_multiple_keys(self, zerog_storage):
        """Test batch_delete with multiple keys"""
        keys = [generate_test_key(f"batch_del_{i}") for i in range(3)]
        values = [f'{{"id": {i}}}' for i in range(3)]

        print(f"\n📝 Writing {len(keys)} keys for batch_delete test...")

        # Write keys
        for key, value in zip(keys, values):
            await zerog_storage.put(key, value)

        # Verify written (wait for sync)
        for key, value in zip(keys, values):
            await wait_for_data_sync(zerog_storage, key, value)

        print(f"✅ Keys written and verified, now batch deleting...")

        # Batch delete
        result = await zerog_storage.batch_delete(keys)
        assert result == len(keys), f"Expected {len(keys)} deletions, got {result}"

        print(f"✅ Batch delete successful, waiting for sync...")

        # Wait for deletes to propagate (same sync time as writes since delete = write empty value)
        for key in keys:
            await wait_for_data_deletion(zerog_storage, key)
            print(f"   ✅ {key} deletion verified")

        print(f"✅ All deletions verified!")


class TestBatchMode:
    """Test batch mode operations (begin_batch, commit_batch)"""

    async def test_batch_mode_basic_flow(self, zerog_storage):
        """Test basic batch mode: begin -> put multiple -> commit -> verify"""
        keys = [generate_test_key(f"batch_mode_{i}") for i in range(3)]
        values = [f'{{"batch": {i}}}' for i in range(3)]

        print(f"\n📦 Starting batch mode...")

        await zerog_storage.begin_batch()

        print(f"📝 Staging {len(keys)} writes in batch...")

        # Stage multiple puts
        for key, value in zip(keys, values):
            result = await zerog_storage.put(key, value)
            assert result is True
            print(f"   Staged: {key}")

        print(f"✅ All writes staged, committing batch...")

        # Commit batch
        commit_result = await zerog_storage.commit_batch()
        assert commit_result is True, "Batch commit failed"

        print(f"✅ Batch committed, waiting for sync...")

        # Verify all data written (wait for sync)
        for key, expected_value in zip(keys, values):
            retrieved = await wait_for_data_sync(zerog_storage, key, expected_value)
            assert retrieved == expected_value, f"Expected {expected_value}, got {retrieved}"
            print(f"   ✅ {key} verified")

        print(f"✅ All batch writes verified!")

    async def test_batch_mode_mixed_operations(self, zerog_storage):
        """Test batch mode with mixed put and delete operations"""
        key_put = generate_test_key("batch_mixed_put")
        key_del = generate_test_key("batch_mixed_del")

        print(f"\n📝 Pre-writing key to delete: {key_del}")

        # Pre-write key to be deleted
        await zerog_storage.put(key_del, '{"to_delete": true}')
        await wait_for_data_sync(zerog_storage, key_del, '{"to_delete": true}')

        print(f"📦 Starting batch with mixed operations...")

        await zerog_storage.begin_batch()

        # Mix put and delete in batch
        await zerog_storage.put(key_put, '{"new": "data"}')
        await zerog_storage.delete(key_del)

        print(f"✅ Operations staged, committing...")

        commit_result = await zerog_storage.commit_batch()
        assert commit_result is True

        print(f"✅ Committed, waiting for sync...")

        # Verify results (wait for sync)
        retrieved_put = await wait_for_data_sync(zerog_storage, key_put, '{"new": "data"}')
        assert retrieved_put == '{"new": "data"}', "Put failed"

        # Wait for delete to propagate (same sync time as write since delete = write empty value)
        await wait_for_data_deletion(zerog_storage, key_del)

        print(f"✅ Mixed operations verified!")

    async def test_nested_batch_raises_error(self, zerog_storage):
        """Test that nested begin_batch raises RuntimeError"""
        print(f"\n📦 Testing nested batch error...")

        await zerog_storage.begin_batch()

        with pytest.raises(RuntimeError, match="already in batch mode"):
            await zerog_storage.begin_batch()

        # Cleanup
        await zerog_storage.commit_batch()

        print(f"✅ Nested batch correctly rejected!")


class TestEdgeCases:
    """Test edge cases and special scenarios"""

    async def test_put_with_large_value(self, zerog_storage):
        """Test put with large JSON value (10KB)"""
        key = generate_test_key("large_value")
        value = '{"data": "' + 'x' * 10000 + '"}'

        print(f"\n📝 Writing large value ({len(value)} bytes)...")

        result = await zerog_storage.put(key, value)
        assert result is True

        print(f"✅ Large write successful, waiting for sync...")

        retrieved = await wait_for_data_sync(zerog_storage, key, value)
        assert retrieved == value, "Large value mismatch"
        assert len(retrieved) == len(value)

        print(f"✅ Large value verified!")

    async def test_put_with_unicode(self, zerog_storage):
        """Test put with Unicode characters"""
        key = generate_test_key("unicode")
        value = '{"message": "Hello 世界 🌍", "emoji": "🚀🎉"}'

        print(f"\n📝 Writing Unicode: {value}")

        result = await zerog_storage.put(key, value)
        assert result is True

        retrieved = await wait_for_data_sync(zerog_storage, key, value)
        assert retrieved == value
        assert "世界" in retrieved
        assert "🌍" in retrieved

        print(f"✅ Unicode preserved correctly!")

    async def test_put_with_special_json(self, zerog_storage):
        """Test put with complex JSON including nested objects and arrays"""
        key = generate_test_key("complex_json")
        value = '''{
            "user": {
                "name": "测试用户",
                "age": 30,
                "tags": ["developer", "tester", "🚀"]
            },
            "metadata": {
                "created": "2026-02-12T10:30:00Z",
                "nested": {
                    "level": 3,
                    "data": [1, 2, 3, 4, 5]
                }
            }
        }'''

        print(f"\n📝 Writing complex JSON...")

        result = await zerog_storage.put(key, value)
        assert result is True

        retrieved = await wait_for_data_sync(zerog_storage, key)

        # Parse both and compare (to handle whitespace differences)
        import json
        assert json.loads(retrieved) == json.loads(value), "Complex JSON mismatch"

        print(f"✅ Complex JSON verified!")

    async def test_concurrent_operations(self, zerog_storage):
        """Test concurrent put operations are handled correctly"""
        keys = [generate_test_key(f"concurrent_{i}") for i in range(5)]
        values = [f'{{"id": {i}}}' for i in range(5)]

        print(f"\n🔀 Running {len(keys)} concurrent writes...")

        # Execute concurrent puts
        tasks = [zerog_storage.put(k, v) for k, v in zip(keys, values)]
        results = await asyncio.gather(*tasks)

        assert all(results), "Some concurrent writes failed"

        print(f"✅ All concurrent writes successful, waiting for sync...")

        # Verify all written correctly (wait for sync)
        for key, value in zip(keys, values):
            retrieved = await wait_for_data_sync(zerog_storage, key, value)
            assert retrieved == value, f"Concurrent write verification failed for {key}"

        print(f"✅ All concurrent writes verified!")


class TestStressTest:
    """Stress tests (optional, can be slow)"""

    @pytest.mark.slow
    async def test_many_sequential_operations(self, zerog_storage):
        """Test many sequential put/get operations"""
        count = 10  # Increase for more thorough testing

        print(f"\n🔄 Running {count} sequential put/get operations...")

        for i in range(count):
            key = generate_test_key(f"seq_{i}")
            value = f'{{"index": {i}}}'

            await zerog_storage.put(key, value)
            retrieved = await wait_for_data_sync(zerog_storage, key, value)
            assert retrieved == value

            if (i + 1) % 5 == 0:
                print(f"   Progress: {i + 1}/{count}")

        print(f"✅ All {count} operations successful!")


# Helper to run tests with proper async support
if __name__ == "__main__":
    # Run with: pytest tests/test_zerog_kv_storage.py -v -s -x
    # -x: stop on first failure (to preserve the failure scene)
    pytest.main([__file__, "-v", "-s", "-x", "--tb=short"])
