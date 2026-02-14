#!/usr/bin/env python3
"""
Standalone Test for Redis KV Storage Iteration and MongoDB Recovery

This script tests the Redis KV Storage iterate_all functionality
without requiring full backend initialization or pytest infrastructure.

Usage:
    python3 tests/standalone_test_redis_kv_recovery.py
"""

import sys
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
from bson import ObjectId

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


class TestRedisKVStorage:
    """Test Redis KV Storage iterate_all functionality"""

    def __init__(self):
        self.passed_tests = []
        self.failed_tests = []

    async def setup(self):
        """Setup Redis KV Storage"""
        from infra_layer.adapters.out.persistence.kv_storage.redis_kv_storage import RedisKVStorage

        self.storage = RedisKVStorage()
        print("✅ Redis KV Storage initialized")

    async def cleanup(self):
        """Cleanup all test keys"""
        print("\n🧹 Cleaning up test keys...")
        try:
            redis = await self.storage._get_redis()
            cursor = 0
            deleted_count = 0

            while True:
                cursor, keys = await redis.scan(cursor=cursor, match="test_*", count=100)
                if keys:
                    await redis.delete(*keys)
                    deleted_count += len(keys)
                if cursor == 0:
                    break

            print(f"✅ Cleaned up {deleted_count} test keys")
        except Exception as e:
            print(f"⚠️  Cleanup error: {e}")

    async def test_redis_iterate_empty(self):
        """Test 1: Iterate empty Redis (only test keys)"""
        test_name = "test_redis_iterate_empty"
        print(f"\n📝 Running: {test_name}")

        try:
            # Clean up first
            await self.cleanup()

            # Iterate and count test keys
            count = 0
            async for key, value in self.storage.iterate_all():
                if key.startswith("test_"):
                    count += 1

            if count == 0:
                print(f"  ✅ PASS: No test keys found (expected)")
                self.passed_tests.append(test_name)
                return True
            else:
                print(f"  ❌ FAIL: Found {count} test keys (expected 0)")
                self.failed_tests.append(test_name)
                return False

        except Exception as e:
            print(f"  ❌ FAIL: Exception: {e}")
            self.failed_tests.append(test_name)
            return False

    async def test_redis_iterate_with_data(self):
        """Test 2: Iterate Redis with test data"""
        test_name = "test_redis_iterate_with_data"
        print(f"\n📝 Running: {test_name}")

        try:
            # Prepare 5 test documents
            test_data = {}
            for i in range(5):
                doc_id = str(ObjectId())
                key = f"test_collection:{doc_id}"

                full_doc = {
                    "id": doc_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "user_id": f"test_user_{i}",
                    "content": f"Test content {i}",
                    "index": i,
                }

                await self.storage.put(key=key, value=json.dumps(full_doc))
                test_data[key] = full_doc

            print(f"  📦 Inserted {len(test_data)} test documents")

            # Iterate and collect
            collected = {}
            async for key, value in self.storage.iterate_all():
                if key.startswith("test_collection:"):
                    collected[key] = json.loads(value)

            # Verify
            if len(collected) == len(test_data):
                # Verify data integrity
                all_match = True
                for key, expected_doc in test_data.items():
                    if key not in collected:
                        print(f"  ❌ Missing key: {key}")
                        all_match = False
                    else:
                        actual_doc = collected[key]
                        if actual_doc["user_id"] != expected_doc["user_id"]:
                            print(f"  ❌ Data mismatch for key: {key}")
                            all_match = False

                if all_match:
                    print(f"  ✅ PASS: All {len(test_data)} documents collected and verified")
                    self.passed_tests.append(test_name)
                    return True
                else:
                    print(f"  ❌ FAIL: Data integrity check failed")
                    self.failed_tests.append(test_name)
                    return False
            else:
                print(f"  ❌ FAIL: Expected {len(test_data)} keys, got {len(collected)}")
                self.failed_tests.append(test_name)
                return False

        except Exception as e:
            print(f"  ❌ FAIL: Exception: {e}")
            import traceback
            traceback.print_exc()
            self.failed_tests.append(test_name)
            return False

    async def test_redis_iterate_large_dataset(self):
        """Test 3: Iterate Redis with larger dataset"""
        test_name = "test_redis_iterate_large_dataset"
        print(f"\n📝 Running: {test_name}")

        try:
            # Prepare 100 test documents
            print(f"  📦 Preparing 100 test documents...")
            for i in range(100):
                doc_id = str(ObjectId())
                key = f"test_large:{doc_id}"

                full_doc = {
                    "id": doc_id,
                    "index": i,
                    "data": f"data_{i}",
                }

                await self.storage.put(key=key, value=json.dumps(full_doc))

            print(f"  📦 Inserted 100 test documents")

            # Iterate and count
            count = 0
            async for key, value in self.storage.iterate_all():
                if key.startswith("test_large:"):
                    count += 1

            if count == 100:
                print(f"  ✅ PASS: Collected all 100 documents")
                self.passed_tests.append(test_name)
                return True
            else:
                print(f"  ❌ FAIL: Expected 100 keys, got {count}")
                self.failed_tests.append(test_name)
                return False

        except Exception as e:
            print(f"  ❌ FAIL: Exception: {e}")
            import traceback
            traceback.print_exc()
            self.failed_tests.append(test_name)
            return False

    async def test_scan_kv_storage_function(self):
        """Test 4: Test _scan_kv_storage function"""
        test_name = "test_scan_kv_storage_function"
        print(f"\n📝 Running: {test_name}")

        try:
            from core.validation.mongodb_data_validator import _scan_kv_storage

            # Prepare test data with collection prefix
            for i in range(3):
                doc_id = str(ObjectId())
                key = f"episodic_memories:{doc_id}"

                full_doc = {
                    "id": doc_id,
                    "user_id": f"scan_test_user_{i}",
                    "content": f"Scan test {i}",
                }

                await self.storage.put(key=key, value=json.dumps(full_doc))

            print(f"  📦 Inserted 3 episodic_memories documents")

            # Scan KV Storage
            docs_by_collection = await _scan_kv_storage(self.storage)

            # Verify
            if "episodic_memories" in docs_by_collection:
                em_docs = docs_by_collection["episodic_memories"]
                if len(em_docs) >= 3:  # May have more from previous tests
                    print(f"  ✅ PASS: Found episodic_memories collection with {len(em_docs)} documents")
                    self.passed_tests.append(test_name)
                    return True
                else:
                    print(f"  ❌ FAIL: Expected at least 3 documents, got {len(em_docs)}")
                    self.failed_tests.append(test_name)
                    return False
            else:
                print(f"  ❌ FAIL: episodic_memories collection not found")
                self.failed_tests.append(test_name)
                return False

        except Exception as e:
            print(f"  ❌ FAIL: Exception: {e}")
            import traceback
            traceback.print_exc()
            self.failed_tests.append(test_name)
            return False

    async def test_lite_data_extraction(self):
        """Test 5: Test Lite data extraction logic"""
        test_name = "test_lite_data_extraction"
        print(f"\n📝 Running: {test_name}")

        try:
            from infra_layer.adapters.out.persistence.kv_storage.lite_model_extractor import LiteModelExtractor
            from infra_layer.adapters.out.persistence.document.memory.episodic_memory import EpisodicMemory

            # Get indexed fields
            indexed_fields = LiteModelExtractor.extract_indexed_fields(EpisodicMemory)
            print(f"  📋 EpisodicMemory indexed fields: {len(indexed_fields)} fields")
            print(f"     Fields: {sorted(indexed_fields)}")

            # Create test document
            doc_id = str(ObjectId())
            full_doc = {
                "id": doc_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "user_id": "lite_test_user",
                "group_id": "lite_test_group",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "episode": "Test episode",
                "keywords": ["test"],
                "importance": 0.5,
                "vector": [0.1] * 768,
                "vector_model": "test-model",
                # Non-indexed fields
                "extra_data": {"should": "not appear"},
                "metadata": {"should": "not appear"},
            }

            # Extract Lite data (same logic as mongodb_data_validator.py)
            lite_data = {}
            for field in indexed_fields:
                if field == 'id':
                    continue

                if field in full_doc:
                    value = full_doc[field]

                    # Convert datetime fields
                    if field in ('created_at', 'updated_at', 'timestamp') and isinstance(value, str):
                        try:
                            value = datetime.fromisoformat(value)
                        except Exception:
                            pass

                    lite_data[field] = value

            # Add _id
            lite_data["_id"] = ObjectId(doc_id)

            print(f"  📋 Lite data fields: {sorted(lite_data.keys())}")
            print(f"     Lite data count: {len(lite_data)}")

            # Verify essential fields exist
            checks = []
            checks.append(("_id in lite_data", "_id" in lite_data))
            checks.append(("user_id in lite_data", "user_id" in lite_data))
            checks.append(("group_id in lite_data", "group_id" in lite_data))

            # Verify non-indexed fields are NOT in Lite data
            checks.append(("extra_data NOT in lite_data", "extra_data" not in lite_data))
            checks.append(("metadata NOT in lite_data", "metadata" not in lite_data))

            # Verify datetime conversion
            if "created_at" in lite_data:
                checks.append(("created_at is datetime", isinstance(lite_data["created_at"], datetime)))

            all_passed = all(passed for _, passed in checks)

            # Print check results
            for check_name, passed in checks:
                status = "✓" if passed else "✗"
                print(f"    {status} {check_name}")

            if all_passed:
                print(f"  ✅ PASS: All Lite data extraction checks passed")
                self.passed_tests.append(test_name)
                return True
            else:
                print(f"  ❌ FAIL: Some Lite data extraction checks failed")
                self.failed_tests.append(test_name)
                return False

        except Exception as e:
            print(f"  ❌ FAIL: Exception: {e}")
            import traceback
            traceback.print_exc()
            self.failed_tests.append(test_name)
            return False

    def print_summary(self):
        """Print test summary"""
        total = len(self.passed_tests) + len(self.failed_tests)
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"Total tests: {total}")
        print(f"✅ Passed: {len(self.passed_tests)}")
        print(f"❌ Failed: {len(self.failed_tests)}")

        if self.failed_tests:
            print("\nFailed tests:")
            for test in self.failed_tests:
                print(f"  - {test}")

        print("=" * 80)

        return len(self.failed_tests) == 0


async def main():
    """Main test runner"""
    print("=" * 80)
    print("Redis KV Storage Iteration Test Suite")
    print("=" * 80)

    tester = TestRedisKVStorage()

    try:
        # Setup
        await tester.setup()

        # Run tests
        await tester.test_redis_iterate_empty()
        await tester.test_redis_iterate_with_data()
        await tester.test_redis_iterate_large_dataset()
        await tester.test_scan_kv_storage_function()
        await tester.test_lite_data_extraction()

        # Cleanup
        await tester.cleanup()

        # Print summary
        all_passed = tester.print_summary()

        return 0 if all_passed else 1

    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
