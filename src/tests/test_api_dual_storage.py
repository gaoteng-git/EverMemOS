#!/usr/bin/env python3
"""
测试API endpoint是否使用双存储

通过HTTP API创建数据，然后验证KV-Storage中是否有数据
"""

import sys
import asyncio
from pathlib import Path
import httpx
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
from common_utils.datetime_utils import get_now_with_timezone, to_iso_format

logger = get_logger(__name__)


async def test_api_dual_storage():
    """通过API创建数据并验证双存储"""
    print("\n" + "="*80)
    print("API Dual Storage 测试")
    print("="*80)

    api_url = "http://localhost:1995/api/v1/memories"

    # 创建多条不同主题的测试消息（触发边界检测）
    now = get_now_with_timezone()
    base_ts = int(now.timestamp() * 1000)

    test_messages = [
        "Hello, I'm testing the dual storage system.",
        "I love playing basketball on weekends.",
        "My favorite team is the Lakers.",
        "I also enjoy reading science fiction novels.",
        "Recently I've been learning Python programming.",
        "The weather is really nice today!",
        "I'm planning to travel to Japan next month.",
    ]

    print("\n📝 Step 1: 通过API发送多条消息（触发边界检测）...")
    print(f"  API URL: {api_url}")
    print(f"  发送 {len(test_messages)} 条消息...")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            for i, content in enumerate(test_messages, 1):
                message_data = {
                    "message_id": f"test_api_dual_storage_{base_ts + i}",
                    "create_time": to_iso_format(now),
                    "sender": "TestUser",
                    "sender_name": "TestUser",
                    "type": "text",
                    "content": content,
                    "group_id": "test_dual_storage_group",
                    "group_name": "Test Dual Storage Group",
                    "scene": "assistant",
                }

                response = await client.post(api_url, json=message_data)
                response.raise_for_status()
                result = response.json()

                status_icon = "✅" if result.get('status') == 'ok' else "❌"
                count = result.get('result', {}).get('count', 0)
                status_msg = f"提取了 {count} 个memory" if count > 0 else "等待积累"

                print(f"  [{i}/{len(test_messages)}] {status_icon} {status_msg}: {content[:40]}...")

                # 短暂延迟，避免消息时间戳完全相同
                await asyncio.sleep(0.5)

            # 等待边界检测和memory extraction完成
            print(f"\n⏳ 等待30秒，让边界检测和memory extraction完成...")
            await asyncio.sleep(30)

    except httpx.ConnectError:
        print(f"  ❌ 无法连接到API服务器 ({api_url})")
        print(f"     请先启动API服务器: uv run python src/run.py")
        return
    except Exception as e:
        print(f"  ❌ API调用失败: {e}")
        import traceback
        traceback.print_exc()
        return

    print(f"\n📊 Step 2: 检查MongoDB中的数据...")

    from infra_layer.adapters.out.persistence.document.memory.episodic_memory import EpisodicMemory
    mongo_collection = EpisodicMemory.get_pymongo_collection()

    # 查找最近创建的文档
    cursor = mongo_collection.find({}).sort("created_at", -1).limit(5)
    docs = await cursor.to_list(length=5)

    print(f"  找到 {len(docs)} 条最新文档")

    if not docs:
        print(f"  ⚠️  MongoDB中没有数据")
        return

    print(f"\n🔍 Step 3: 检查这些文档是否在KV-Storage中...")

    from infra_layer.adapters.out.persistence.kv_storage.kv_storage_interface import (
        KVStorageInterface,
    )
    kv_storage = get_bean_by_type(KVStorageInterface)

    found_in_kv = 0
    missing_from_kv = 0

    for i, doc in enumerate(docs, 1):
        doc_id = str(doc['_id'])
        created_at = doc.get('created_at', 'N/A')

        kv_value = await kv_storage.get(key=doc_id)

        if kv_value is not None:
            found_in_kv += 1
            print(f"  [{i}] ✅ ID {doc_id}: EXISTS in KV-Storage")
            print(f"       Created: {created_at}")

            import json
            full_data = json.loads(kv_value)
            has_subject = 'subject' in full_data and full_data['subject']
            has_summary = 'summary' in full_data and full_data['summary']
            has_episode = 'episode' in full_data and full_data['episode']
            print(f"       Fields: subject={has_subject}, summary={has_summary}, episode={has_episode}")
        else:
            missing_from_kv += 1
            print(f"  [{i}] ❌ ID {doc_id}: MISSING from KV-Storage")
            print(f"       Created: {created_at}")

            # Check MongoDB fields
            mongo_fields = []
            if 'subject' in doc and doc['subject']:
                mongo_fields.append('subject')
            if 'summary' in doc and doc['summary']:
                mongo_fields.append('summary')
            if 'episode' in doc and doc['episode']:
                mongo_fields.append('episode')

            if mongo_fields:
                print(f"       MongoDB has: {', '.join(mongo_fields)}")
            else:
                print(f"       MongoDB Lite (missing: subject, summary, episode)")

    # Summary
    print("\n" + "="*80)
    print("测试结果")
    print("="*80)
    print(f"  检查的文档数: {len(docs)}")
    print(f"  ✅ KV-Storage中存在: {found_in_kv}")
    print(f"  ❌ KV-Storage中缺失: {missing_from_kv}")

    if found_in_kv > 0:
        print(f"\n  🎉 成功！API使用了双存储")
        print(f"     {found_in_kv}/{len(docs)} 文档有完整数据在KV-Storage")
    else:
        print(f"\n  ❌ 失败！API没有使用双存储")
        print(f"     所有 {len(docs)} 文档都没有数据在KV-Storage")
        print(f"\n可能的原因：")
        print(f"  1. API服务器需要重启以加载最新代码")
        print(f"  2. Repository没有正确初始化DualStorageMixin")
        print(f"  3. KV存储写入失败（检查API服务器日志）")


if __name__ == "__main__":
    asyncio.run(test_api_dual_storage())
