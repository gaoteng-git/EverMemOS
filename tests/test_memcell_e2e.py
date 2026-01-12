#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
End-to-End tests for MemCell API with KV-Storage integration

Tests the KV-Storage dual-write and validation through actual API calls.
Requires backend server to be running before executing tests.

TEST FOCUS:
- POST /api/v1/memories creates **MemCell** with dual-write to MongoDB + KV-Storage
- Tests verify successful API calls, not data retrieval
- Data consistency validation is checked via backend logs (see analyze_kv_consistency.py)

IMPORTANT:
- Test messages use DIFFERENT topics to trigger boundary detection
- Similar messages stay in Redis cache; different topics trigger MemCell creation
- After tests, run: python tests/analyze_kv_consistency.py
"""

import asyncio
import aiohttp
import uuid
from datetime import datetime
from typing import List, Dict, Any

# Test configuration
BASE_URL = "http://localhost:1995"
API_BASE = f"{BASE_URL}/api/v1"
TEST_USER_PREFIX = "e2e_test_user_"


class MemCellE2ETest:
    """End-to-end test for MemCell API"""

    def __init__(self):
        self.base_url = API_BASE
        self.test_user_id = f"{TEST_USER_PREFIX}{uuid.uuid4().hex[:8]}"
        self.created_memory_ids = []

    async def create_memory(
        self, session: aiohttp.ClientSession, summary: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Create a memory via POST /api/v1/memories

        This calls append_memcell in the repository, which performs:
        - Dual-write to MongoDB and KV-Storage
        - KV-Storage validation
        """
        # Generate unique message_id for this test message
        message_id = f"msg_{uuid.uuid4().hex[:8]}"

        # Build payload in the format expected by memorize_single_message API
        payload = {
            "message_id": message_id,
            "create_time": datetime.now().isoformat(),
            "sender": self.test_user_id,
            "sender_name": f"Test User {self.test_user_id[:8]}",
            "content": summary,
            "group_id": kwargs.get("group_id", f"group_{self.test_user_id}"),
            "group_name": kwargs.get("group_name", "E2E Test Group"),
        }

        # Add any additional fields from kwargs (e.g., refer_list)
        for key in ["refer_list"]:
            if key in kwargs:
                payload[key] = kwargs[key]

        async with session.post(f"{self.base_url}/memories", json=payload) as resp:
            # Accept both 200 (OK) and 202 (Accepted - async processing)
            assert resp.status in [200, 202], f"Failed to create memory: {resp.status}"
            data = await resp.json()
            memory_id = data.get("id") or data.get("event_id")
            if memory_id:
                self.created_memory_ids.append(memory_id)
            return data


    async def cleanup(self, session: aiohttp.ClientSession):
        """
        Clean up all test data to ensure no data remains in MongoDB

        This calls delete_by_user_id in the repository, which performs:
        - Batch delete from MongoDB
        - Batch delete from KV-Storage
        """
        # Delete by user_id (if API supports it)
        try:
            async with session.delete(
                f"{self.base_url}/memories", params={"user_id": self.test_user_id}
            ) as resp:
                print(f"✅ Cleanup: deleted via user_id, status: {resp.status}")
                return
        except Exception as e:
            print(f"⚠️ Cleanup via user_id failed: {e}")

        # Fallback: delete each memory individually
        for memory_id in self.created_memory_ids:
            try:
                async with session.delete(
                    f"{self.base_url}/memories/{memory_id}"
                ) as resp:
                    print(f"✅ Cleanup: deleted memory {memory_id}, status: {resp.status}")
            except Exception as e:
                print(f"⚠️ Failed to delete memory {memory_id}: {e}")

    async def test_create_single_memory(self):
        """
        Test 1: Create a single memory via POST

        Covered repository functions:
        - append_memcell (via POST) - tests dual-write to MongoDB + KV-Storage

        Note:
        - POST creates MemCell (raw conversation record)
        - Uses distinct topic to trigger boundary detection
        - Data consistency validation checked via backend logs
        """
        print("\n" + "=" * 70)
        print("Test 1: Create a single memory via POST")
        print("=" * 70)

        async with aiohttp.ClientSession() as session:
            try:
                # Create a memory
                print(f"\n➡️  Creating memory for user: {self.test_user_id}")
                created = await self.create_memory(
                    session,
                    summary="I love playing basketball on weekends",
                )
                print(f"✅ Created memory via POST endpoint")
                print(f"   Response: {created}")

                # Wait for async processing (clustering, boundary detection)
                print(f"\n⏳ Waiting 30 seconds for async processing...")
                await asyncio.sleep(30)

                print("\n✅ Test 1 PASSED: Memory creation successful")
                print("   Covered functions:")
                print("   - append_memcell (dual-write to MongoDB + KV-Storage)")

            finally:
                # Cleanup attempt
                print("\n🧹 Attempting cleanup...")
                await self.cleanup(session)
                print("⚠️  Cleanup completed (manual DB cleanup may be needed)")

    async def test_create_multiple_memories(self):
        """
        Test 2: Create multiple memories via POST

        Covered repository functions:
        - append_memcell (via POST) - multiple times with dual-write

        Note:
        - Uses DIFFERENT topics (hiking, weather, universe) to trigger boundary detection
        - Similar topics stay in Redis cache without triggering MemCell
        - Data consistency validation checked via backend logs
        """
        print("\n" + "=" * 70)
        print("Test 2: Create multiple memories via POST")
        print("=" * 70)

        async with aiohttp.ClientSession() as session:
            try:
                # Create multiple memories with DIFFERENT topics to trigger boundary detection
                print(f"\n➡️  Creating 3 memories for user: {self.test_user_id}")

                topics = [
                    "I enjoy hiking in the mountains during summer",
                    "The weather is very nice today",
                    "The universe is expanding at an accelerating rate",
                ]

                for i, topic in enumerate(topics):
                    await self.create_memory(
                        session,
                        summary=topic,
                    )
                    print(f"✅ Created memory {i + 1}/3: {topic[:40]}...")
                    await asyncio.sleep(5)  # Small delay between creates

                # Wait for async processing
                print(f"\n⏳ Waiting 30 seconds for async processing...")
                await asyncio.sleep(30)

                print("\n✅ Test 2 PASSED: Multiple memory creation successful")
                print("   Covered functions:")
                print("   - append_memcell (multiple dual-writes to MongoDB + KV-Storage)")

            finally:
                # Cleanup attempt
                print("\n🧹 Attempting cleanup...")
                await self.cleanup(session)
                print("⚠️  Cleanup completed (manual DB cleanup may be needed)")

    async def test_create_batch_memories(self):
        """
        Test 3: Create batch memories with different topics

        Covered repository functions:
        - append_memcell (via POST) - multiple times

        Note:
        - Uses 5 DIFFERENT topics to trigger boundary detection
        - Each topic change ensures MemCell creation instead of Redis caching
        - Data consistency validation checked via backend logs
        """
        print("\n" + "=" * 70)
        print("Test 3: Create batch memories with different topics")
        print("=" * 70)

        async with aiohttp.ClientSession() as session:
            try:
                # Create memories with DIFFERENT topics to trigger boundary detection
                print(f"\n➡️  Creating 5 memories for user: {self.test_user_id}")

                topics = [
                    "I love reading science fiction novels",
                    "Coffee is my favorite morning beverage",
                    "The Eiffel Tower is located in Paris",
                    "Python is a popular programming language",
                    "The moon orbits around the Earth",
                ]

                for i, topic in enumerate(topics):
                    await self.create_memory(
                        session,
                        summary=topic,
                    )
                    print(f"✅ Created memory {i + 1}/5: {topic[:40]}...")
                    await asyncio.sleep(5)  # Small delay between creates

                # Wait for async processing
                print(f"\n⏳ Waiting 30 seconds for async processing...")
                await asyncio.sleep(30)

                print("\n✅ Test 3 PASSED: Batch memory creation successful")
                print("   Covered functions:")
                print("   - append_memcell (multiple dual-writes to MongoDB + KV-Storage)")

            finally:
                # Cleanup attempt
                print("\n🧹 Attempting cleanup...")
                await self.cleanup(session)
                print("⚠️  Cleanup completed (manual DB cleanup may be needed)")

    async def run_all_tests(self):
        """Run all E2E tests"""
        print("\n" + "=" * 70)
        print("🚀 Starting End-to-End Tests for MemCell API")
        print("=" * 70)
        print(f"Base URL: {self.base_url}")
        print(f"Test User ID: {self.test_user_id}")
        print("=" * 70)

        try:
            # Test 1
            await self.test_create_single_memory()

            # Reset for next test
            self.created_memory_ids = []
            self.test_user_id = f"{TEST_USER_PREFIX}{uuid.uuid4().hex[:8]}"

            # Test 2
            await self.test_create_multiple_memories()

            # Reset for next test
            self.created_memory_ids = []
            self.test_user_id = f"{TEST_USER_PREFIX}{uuid.uuid4().hex[:8]}"

            # Test 3
            await self.test_create_batch_memories()

            print("\n" + "=" * 70)
            print("🎉 All E2E tests PASSED!")
            print("=" * 70)
            print("\n✅ Summary:")
            print("   - 3 test scenarios completed successfully")
            print("   - Created test memories via POST /api/v1/memories")
            print("   - Total API calls: 9 POST requests (1 + 3 + 5)")
            print("   - Total wait time: ~90 seconds for async processing")
            print("\n✅ Covered Repository Functions:")
            print("   1. append_memcell - Dual-write to MongoDB + KV-Storage")
            print("      (Tested via POST /api/v1/memories endpoint)")
            print("\n⚠️  Important Notes:")
            print("   - POST creates MemCell (raw conversation records)")
            print("   - MemCell → Memory processing is asynchronous (clustering, consolidation)")
            print("   - Messages use DIFFERENT topics to trigger boundary detection")
            print("     (Similar topics stay in Redis cache; different topics trigger MemCell creation)")
            print("   - Each test waits 30 seconds for async processing")
            print("\n🔍 Data Consistency Validation:")
            print("   - Run the log analyzer to check MongoDB <-> KV-Storage consistency:")
            print("     python tests/analyze_kv_consistency.py")
            print("\n🧹 Cleanup:")
            print("   - No DELETE endpoint available - manual cleanup required")
            print("   - MongoDB collections: memcells, core_memories, foresight_records, episodic_memories")
            print("   - Filter by user_id prefix: 'e2e_test_user_*'")
            print("   - Example: db.memcells.deleteMany({sender: /^e2e_test_user_/})")
            print("=" * 70)

        except AssertionError as e:
            print(f"\n❌ Test failed: {e}")
            raise
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            raise


async def main():
    """Main entry point"""
    test = MemCellE2ETest()
    await test.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
