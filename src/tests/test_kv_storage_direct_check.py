#!/usr/bin/env python3
"""
Direct KV Storage Check - Verify if data actually exists in KV-Storage

This script directly checks the KV storage to see if documents exist there.
"""

import sys
import asyncio
from pathlib import Path

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
    """Check if KV storage has data for recent documents"""
    print("\n" + "="*80)
    print("KV Storage Direct Check")
    print("="*80)

    from infra_layer.adapters.out.persistence.kv_storage.kv_storage_interface import (
        KVStorageInterface,
    )
    from infra_layer.adapters.out.persistence.repository.episodic_memory_raw_repository import (
        EpisodicMemoryRawRepository,
    )

    # Get repositories and KV storage
    kv_storage = get_bean_by_type(KVStorageInterface)
    mongo_repo = get_bean_by_type(EpisodicMemoryRawRepository)

    # Get latest 5 documents from MongoDB (directly using PyMongo, no validation)
    print("\n📊 Step 1: Get latest documents from MongoDB...")

    # Use PyMongo directly to avoid Pydantic validation
    from infra_layer.adapters.out.persistence.document.memory.episodic_memory import EpisodicMemory
    mongo_collection = EpisodicMemory.get_pymongo_collection()

    cursor = mongo_collection.find({}).sort("created_at", -1).limit(5)
    mongo_docs_raw = await cursor.to_list(length=5)

    print(f"  Found {len(mongo_docs_raw)} documents in MongoDB")

    if not mongo_docs_raw:
        print("  ⚠️  No documents found in MongoDB!")
        return

    # Check each document in KV storage
    print("\n🔍 Step 2: Check if these documents exist in KV-Storage...")

    found_in_kv = 0
    missing_from_kv = 0

    for i, doc in enumerate(mongo_docs_raw, 1):
        doc_id = str(doc['_id'])
        kv_value = await kv_storage.get(key=doc_id)

        if kv_value is not None:
            found_in_kv += 1
            print(f"  [{i}] ✅ ID {doc_id}: EXISTS in KV-Storage ({len(kv_value)} bytes)")

            # Parse and check fields
            import json
            full_data = json.loads(kv_value)
            has_subject = 'subject' in full_data and full_data['subject']
            has_summary = 'summary' in full_data and full_data['summary']
            has_episode = 'episode' in full_data and full_data['episode']

            status = "✅ FULL" if (has_subject and has_summary and has_episode) else "⚠️  PARTIAL"
            print(f"       {status}: subject={has_subject}, summary={has_summary}, episode={has_episode}")
        else:
            missing_from_kv += 1
            print(f"  [{i}] ❌ ID {doc_id}: MISSING from KV-Storage")

            # Check what's in MongoDB
            mongo_fields = []
            if 'subject' in doc and doc['subject']:
                mongo_fields.append('subject')
            if 'summary' in doc and doc['summary']:
                mongo_fields.append('summary')
            if 'episode' in doc and doc['episode']:
                mongo_fields.append('episode')

            if mongo_fields:
                print(f"       (But MongoDB Lite has: {', '.join(mongo_fields)})")
            else:
                print(f"       (MongoDB Lite is missing: subject, summary, episode)")

    # Summary
    print("\n" + "="*80)
    print("Summary")
    print("="*80)
    print(f"  Total documents checked: {len(mongo_docs_raw)}")
    print(f"  ✅ Found in KV-Storage: {found_in_kv}")
    print(f"  ❌ Missing from KV-Storage: {missing_from_kv}")

    if found_in_kv > 0:
        print(f"\n  🎉 SUCCESS: Dual storage WRITE is working!")
        print(f"     {found_in_kv} out of {len(mongo_docs_raw)} documents have full data in KV-Storage")
    else:
        print(f"\n  ❌ FAILURE: Dual storage WRITE is NOT working!")
        print(f"     None of the {len(mongo_docs_raw)} documents have data in KV-Storage")
        print(f"     This suggests:")
        print(f"     1. DualStorageMixin monkey patching is not active")
        print(f"     2. Or KV storage writes are failing silently")
        print(f"     3. Or documents were created before dual storage was enabled")


if __name__ == "__main__":
    asyncio.run(main())
