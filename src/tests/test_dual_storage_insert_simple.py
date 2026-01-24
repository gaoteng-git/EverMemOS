#!/usr/bin/env python3
"""
Simple Test: Direct Insert to Verify Monkey Patching

This test directly inserts a document using Repository and checks if dual storage works.
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# IMPORTANT: Must setup environment and DI BEFORE importing repositories
from common_utils.load_env import setup_environment
setup_environment(load_env_file_name=".env", check_env_var="MONGODB_HOST")

# Setup all (DI container, etc.)
from application_startup import setup_all
setup_all(load_entrypoints=False)

from core.di.utils import get_bean_by_type
from core.observation.logger import get_logger

logger = get_logger(__name__)


async def main():
    """Simple insert test"""
    print("\n" + "="*80)
    print("Simple Dual Storage Insert Test")
    print("="*80)

    from infra_layer.adapters.out.persistence.kv_storage.kv_storage_interface import (
        KVStorageInterface,
    )
    from infra_layer.adapters.out.persistence.repository.episodic_memory_raw_repository import (
        EpisodicMemoryRawRepository,
    )
    from infra_layer.adapters.out.persistence.document.memory.episodic_memory import (
        EpisodicMemory,
    )
    from common_utils.datetime_utils import get_now_with_timezone

    # Get services
    kv_storage = get_bean_by_type(KVStorageInterface)
    repo = get_bean_by_type(EpisodicMemoryRawRepository)

    print("\n📝 Step 1: Check if document class is patched...")
    has_original_insert = hasattr(EpisodicMemory, '_original_insert')
    print(f"  EpisodicMemory._original_insert exists: {has_original_insert}")
    if has_original_insert:
        print("  ✅ Document class has been monkey-patched!")
    else:
        print("  ❌ Document class has NOT been monkey-patched!")
        print("     This means DualStorageMixin.__init__ was never called!")
        return

    print("\n📝 Step 2: Create and insert a test document...")

    # Create test document
    now = get_now_with_timezone()
    test_doc = EpisodicMemory(
        user_id="test_user_001",
        group_id="test_group",
        timestamp=now,
        subject="Test Subject",
        summary="Test Summary",
        episode="Test Episode - This is the full content",
        event_type="test",
        vector=[0.1] * 1536,
    )

    print(f"  Created test document with fields:")
    print(f"    - subject: {test_doc.subject}")
    print(f"    - summary: {test_doc.summary}")
    print(f"    - episode: {test_doc.episode}")

    # Insert using repository
    result = await repo.append_episodic_memory(test_doc)

    if result is None:
        print("  ❌ Insert failed!")
        return

    doc_id = str(result.id)
    print(f"  ✅ Inserted successfully, ID: {doc_id}")

    print("\n📝 Step 3: Check if data exists in KV-Storage...")

    kv_value = await kv_storage.get(key=doc_id)

    if kv_value is None:
        print(f"  ❌ FAILED: Document NOT found in KV-Storage!")
        print(f"     This means the monkey-patched insert() is NOT being called!")

        # Check MongoDB
        mongo_collection = EpisodicMemory.get_pymongo_collection()
        from bson import ObjectId
        mongo_doc = await mongo_collection.find_one({"_id": ObjectId(doc_id)})

        if mongo_doc:
            print(f"\n  MongoDB document fields: {list(mongo_doc.keys())}")
            has_subject = 'subject' in mongo_doc and mongo_doc['subject']
            has_summary = 'summary' in mongo_doc and mongo_doc['summary']
            has_episode = 'episode' in mongo_doc and mongo_doc['episode']
            print(f"    - subject: {has_subject}")
            print(f"    - summary: {has_summary}")
            print(f"    - episode: {has_episode}")

            if has_subject and has_summary and has_episode:
                print(f"  ⚠️  MongoDB has FULL data (not Lite)!")
                print(f"     This suggests original insert() was called, not wrapped version!")
    else:
        print(f"  ✅ SUCCESS: Document found in KV-Storage ({len(kv_value)} bytes)")

        import json
        full_data = json.loads(kv_value)
        has_subject = 'subject' in full_data and full_data['subject']
        has_summary = 'summary' in full_data and full_data['summary']
        has_episode = 'episode' in full_data and full_data['episode']

        print(f"    - subject: {has_subject}")
        print(f"    - summary: {has_summary}")
        print(f"    - episode: {has_episode}")

        status = "✅ FULL" if (has_subject and has_summary and has_episode) else "⚠️  PARTIAL"
        print(f"  {status} data in KV-Storage")

    # Cleanup
    print(f"\n📝 Step 4: Cleanup...")
    await kv_storage.delete(key=doc_id)
    await repo.delete_by_event_id(doc_id, "test_user_001")
    print(f"  ✅ Cleanup complete")


if __name__ == "__main__":
    asyncio.run(main())
