#!/usr/bin/env python3
"""
进程内双存储测试

直接在同一进程中创建和读取数据，避免跨进程问题。
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
from common_utils.datetime_utils import get_now_with_timezone

logger = get_logger(__name__)


async def test_in_process():
    """在同一进程中测试双存储"""
    print("\n" + "="*80)
    print("进程内双存储测试")
    print("="*80)

    from infra_layer.adapters.out.persistence.repository.episodic_memory_raw_repository import (
        EpisodicMemoryRawRepository,
    )
    from infra_layer.adapters.out.persistence.document.memory.episodic_memory import (
        EpisodicMemory,
    )
    from infra_layer.adapters.out.persistence.kv_storage.kv_storage_interface import (
        KVStorageInterface,
    )

    # Get services
    kv_storage = get_bean_by_type(KVStorageInterface)
    repo = get_bean_by_type(EpisodicMemoryRawRepository)

    print(f"\n✅ KV-Storage类型: {type(kv_storage).__name__}")

    print(f"\n📝 Step 1: 创建测试文档...")

    # Create test document
    now = get_now_with_timezone()
    test_doc = EpisodicMemory(
        user_id="test_in_process",
        group_id="test_group",
        timestamp=now,
        subject="进程内测试 Subject",
        summary="进程内测试 Summary",
        episode="进程内测试 Episode - 验证同进程内双存储是否工作",
        event_type="test",
        vector=[0.1] * 1536,
    )

    # Insert
    result = await repo.append_episodic_memory(test_doc)
    if result is None:
        print("❌ 插入失败!")
        return

    doc_id = str(result.id)
    print(f"✅ 插入成功, ID: {doc_id}")

    print(f"\n🔍 Step 2: 立即在同一进程中检查KV-Storage...")

    kv_value = await kv_storage.get(key=doc_id)

    if kv_value is None:
        print(f"❌ 失败: 文档不在KV-Storage中!")
        print(f"   这说明双存储WRITE失败")

        # 检查MongoDB
        mongo_collection = EpisodicMemory.get_pymongo_collection()
        from bson import ObjectId
        mongo_doc = await mongo_collection.find_one({"_id": ObjectId(doc_id)})

        if mongo_doc:
            print(f"\n  MongoDB文档字段: {list(mongo_doc.keys())}")
            has_subject = 'subject' in mongo_doc and mongo_doc['subject']
            has_summary = 'summary' in mongo_doc and mongo_doc['summary']
            has_episode = 'episode' in mongo_doc and mongo_doc['episode']
            print(f"    - subject: {has_subject}")
            print(f"    - summary: {has_summary}")
            print(f"    - episode: {has_episode}")

            if has_subject and has_summary and has_episode:
                print(f"  ⚠️  MongoDB有完整数据（应该是Lite）")
            else:
                print(f"  ✅ MongoDB只有Lite数据（正确）")
    else:
        print(f"✅ 成功: 文档在KV-Storage中 ({len(kv_value)} bytes)")

        import json
        full_data = json.loads(kv_value)
        has_subject = 'subject' in full_data and full_data['subject']
        has_summary = 'summary' in full_data and full_data['summary']
        has_episode = 'episode' in full_data and full_data['episode']

        print(f"  完整数据字段:")
        print(f"    - subject: {has_subject} = {full_data.get('subject', 'N/A')[:30]}...")
        print(f"    - summary: {has_summary} = {full_data.get('summary', 'N/A')[:30]}...")
        print(f"    - episode: {has_episode} = {full_data.get('episode', 'N/A')[:30]}...")

        if has_subject and has_summary and has_episode:
            print(f"\n🎉 ✅ 双存储WRITE成功!")

    print(f"\n📖 Step 3: 通过Repository读取（测试READ）...")

    # Read back using repository
    query = repo.model.find({"_id": result.id})
    docs = await query.limit(1).to_list()

    if not docs:
        print(f"❌ 失败: 查询返回0条文档")
        print(f"   这说明DualStorageQueryProxy过滤了文档（KV miss）")
    else:
        retrieved_doc = docs[0]
        print(f"✅ 成功: 读取到1条文档")

        has_subject = hasattr(retrieved_doc, 'subject') and retrieved_doc.subject
        has_summary = hasattr(retrieved_doc, 'summary') and retrieved_doc.summary
        has_episode = hasattr(retrieved_doc, 'episode') and retrieved_doc.episode

        print(f"  读取到的文档字段:")
        print(f"    - subject: {has_subject}")
        print(f"    - summary: {has_summary}")
        print(f"    - episode: {has_episode}")

        if has_subject and has_summary and has_episode:
            print(f"\n🎉 ✅ 双存储READ成功!")
            print(f"   ✅ 完整数据从KV-Storage加载成功")
        else:
            print(f"\n❌ 双存储READ失败")
            print(f"   ⚠️  读取到的是Lite数据")

    # Cleanup
    print(f"\n🧹 Step 4: 清理...")
    await kv_storage.delete(key=doc_id)
    await repo.delete_by_event_id(doc_id, "test_in_process")
    print(f"✅ 清理完成")

    print(f"\n" + "="*80)
    print(f"测试完成")
    print(f"="*80)


if __name__ == "__main__":
    asyncio.run(test_in_process())
