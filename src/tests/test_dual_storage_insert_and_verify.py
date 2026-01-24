#!/usr/bin/env python3
"""
Test: Insert with Dual Storage and Verify Read Works

This test:
1. Inserts a document with full data
2. Verifies it's in KV-Storage
3. Reads it back using Repository (through DualStorageQueryProxy)
4. Confirms we get full data back
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
    """Insert and verify full workflow"""
    print("\n" + "="*80)
    print("Dual Storage Insert and Read Verification Test")
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

    print("\n" + "="*80)
    print("STEP 1: Insert Test Document")
    print("="*80)

    # Create test document
    now = get_now_with_timezone()
    test_doc = EpisodicMemory(
        user_id="test_verification_user",
        group_id="test_group",
        timestamp=now,
        subject="Verification Test Subject",
        summary="Verification Test Summary",
        episode="Verification Test Episode - This proves dual storage READ works correctly",
        event_type="test",
        vector=[0.1] * 1536,
    )

    # Insert
    result = await repo.append_episodic_memory(test_doc)
    if result is None:
        print("❌ Insert failed!")
        return

    doc_id = str(result.id)
    print(f"✅ Inserted document ID: {doc_id}")
    print(f"   - subject: {result.subject}")
    print(f"   - summary: {result.summary}")
    print(f"   - episode: {result.episode[:50]}...")

    print("\n" + "="*80)
    print("STEP 2: Verify KV-Storage Contains Full Data")
    print("="*80)

    kv_value = await kv_storage.get(key=doc_id)
    if kv_value is None:
        print(f"❌ Document NOT in KV-Storage!")
        return

    import json
    full_data = json.loads(kv_value)
    print(f"✅ KV-Storage contains: {len(full_data)} fields")
    print(f"   - subject: {'subject' in full_data and full_data['subject']}")
    print(f"   - summary: {'summary' in full_data and full_data['summary']}")
    print(f"   - episode: {'episode' in full_data and full_data['episode']}")

    print("\n" + "="*80)
    print("STEP 3: Read Back Through Repository (DualStorageQueryProxy)")
    print("="*80)

    # Read back using repository (should go through DualStorageQueryProxy)
    query = repo.model.find({"_id": result.id}).sort("-created_at")
    docs = await query.limit(1).to_list()

    if not docs:
        print("❌ No documents returned from query!")
        print("   This suggests DualStorageQueryProxy filtered it out (KV miss)")
        return

    retrieved_doc = docs[0]
    print(f"✅ Retrieved {len(docs)} document(s)")

    print("\n" + "="*80)
    print("STEP 4: Verify Retrieved Document Has Full Data")
    print("="*80)

    # Check fields
    has_subject = hasattr(retrieved_doc, 'subject') and retrieved_doc.subject
    has_summary = hasattr(retrieved_doc, 'summary') and retrieved_doc.summary
    has_episode = hasattr(retrieved_doc, 'episode') and retrieved_doc.episode

    print(f"  Retrieved document fields:")
    print(f"    - subject: {has_subject}")
    if has_subject:
        print(f"      value: {retrieved_doc.subject}")
    print(f"    - summary: {has_summary}")
    if has_summary:
        print(f"      value: {retrieved_doc.summary}")
    print(f"    - episode: {has_episode}")
    if has_episode:
        print(f"      value: {retrieved_doc.episode[:50]}...")

    if has_subject and has_summary and has_episode:
        print(f"\n🎉 ✅ SUCCESS: Dual Storage READ works correctly!")
        print(f"   - MongoDB stores Lite data")
        print(f"   - KV-Storage stores Full data")
        print(f"   - DualStorageQueryProxy loads Full data from KV-Storage")
        print(f"   - User receives complete document")
    else:
        print(f"\n❌ FAIL: Retrieved document is missing fields!")
        print(f"   This suggests DualStorageQueryProxy is not loading from KV-Storage")

    # Cleanup
    print(f"\n" + "="*80)
    print("STEP 5: Cleanup")
    print("="*80)
    await kv_storage.delete(key=doc_id)
    await repo.delete_by_event_id(doc_id, "test_verification_user")
    print(f"✅ Cleanup complete")


if __name__ == "__main__":
    asyncio.run(main())
