#!/usr/bin/env python3
"""
迁移脚本：将现有MongoDB数据同步到KV-Storage

用途：
- 为双存储启用前创建的旧数据补充KV存储
- 让旧数据也能被DualStorageQueryProxy正确读取

使用方法：
    uv run python src/bootstrap.py src/devops_scripts/migrate_existing_data_to_kv.py
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


async def migrate_collection(
    collection_name: str,
    model_class,
    repository_class
):
    """
    迁移单个集合的数据到KV-Storage

    Args:
        collection_name: 集合名称（用于显示）
        model_class: Document模型类
        repository_class: Repository类
    """
    print(f"\n{'='*80}")
    print(f"迁移集合: {collection_name}")
    print(f"{'='*80}")

    from infra_layer.adapters.out.persistence.kv_storage.kv_storage_interface import (
        KVStorageInterface,
    )

    kv_storage = get_bean_by_type(KVStorageInterface)

    # 使用PyMongo直接查询，避免Pydantic验证
    mongo_collection = model_class.get_pymongo_collection()
    cursor = mongo_collection.find({})

    total_docs = await mongo_collection.count_documents({})
    print(f"📊 MongoDB中共有 {total_docs} 条文档")

    if total_docs == 0:
        print(f"  ℹ️  集合为空，跳过")
        return

    migrated_count = 0
    already_exists_count = 0
    failed_count = 0
    missing_required_fields_count = 0

    batch_size = 100
    processed = 0

    async for doc in cursor:
        processed += 1
        doc_id = str(doc['_id'])

        try:
            # 检查KV中是否已存在
            existing = await kv_storage.get(key=doc_id)
            if existing is not None:
                already_exists_count += 1
                if processed % batch_size == 0:
                    print(f"  进度: {processed}/{total_docs} (已存在: {already_exists_count})")
                continue

            # 检查是否有必需字段
            # 根据不同的集合检查不同的字段
            required_fields_check = True
            if collection_name == "episodic_memories":
                # summary和episode是required字段
                if not doc.get('summary') or not doc.get('episode'):
                    required_fields_check = False
                    missing_required_fields_count += 1
            elif collection_name == "event_log_records":
                # atomic_fact是required字段
                if not doc.get('atomic_fact'):
                    required_fields_check = False
                    missing_required_fields_count += 1
            elif collection_name == "foresight_records":
                # content是required字段
                if not doc.get('content'):
                    required_fields_check = False
                    missing_required_fields_count += 1

            if not required_fields_check:
                # 缺少必需字段，跳过
                if processed % batch_size == 0:
                    print(f"  进度: {processed}/{total_docs} (缺少字段: {missing_required_fields_count})")
                continue

            # 将文档存入KV-Storage
            import json
            from bson import ObjectId
            from datetime import datetime

            def json_serializer(obj):
                """Custom JSON serializer for ObjectId and datetime"""
                if isinstance(obj, ObjectId):
                    return str(obj)
                elif isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Type {type(obj)} not serializable")

            # 添加id字段（从_id转换）
            doc['id'] = doc['_id']
            # 移除_id（避免序列化问题）
            doc_copy = {k: v for k, v in doc.items() if k != '_id'}

            kv_value = json.dumps(doc_copy, default=json_serializer)
            await kv_storage.put(key=doc_id, value=kv_value)

            migrated_count += 1

            if processed % batch_size == 0:
                print(f"  进度: {processed}/{total_docs} (已迁移: {migrated_count})")

        except Exception as e:
            failed_count += 1
            logger.error(f"  ❌ 迁移失败 {doc_id}: {e}")

    # 最终统计
    print(f"\n📈 迁移结果:")
    print(f"  ✅ 新迁移: {migrated_count}")
    print(f"  ℹ️  已存在: {already_exists_count}")
    print(f"  ⚠️  缺少必需字段（跳过）: {missing_required_fields_count}")
    print(f"  ❌ 失败: {failed_count}")
    print(f"  📊 总计: {total_docs}")


async def main():
    """主迁移流程"""
    print("\n" + "🔄"*40)
    print("MongoDB数据迁移到KV-Storage")
    print("为旧数据补充双存储支持")
    print("🔄"*40)

    from infra_layer.adapters.out.persistence.document.memory.episodic_memory import (
        EpisodicMemory,
    )
    from infra_layer.adapters.out.persistence.document.memory.event_log_record import (
        EventLogRecord,
    )
    from infra_layer.adapters.out.persistence.document.memory.foresight_record import (
        ForesightRecord,
    )
    from infra_layer.adapters.out.persistence.document.memory.conversation_meta import (
        ConversationMeta,
    )
    from infra_layer.adapters.out.persistence.repository.episodic_memory_raw_repository import (
        EpisodicMemoryRawRepository,
    )
    from infra_layer.adapters.out.persistence.repository.event_log_record_raw_repository import (
        EventLogRecordRawRepository,
    )
    from infra_layer.adapters.out.persistence.repository.foresight_record_repository import (
        ForesightRecordRawRepository,
    )
    from infra_layer.adapters.out.persistence.repository.conversation_meta_raw_repository import (
        ConversationMetaRawRepository,
    )

    try:
        # 迁移4个主要集合
        await migrate_collection(
            "episodic_memories",
            EpisodicMemory,
            EpisodicMemoryRawRepository
        )

        await migrate_collection(
            "event_log_records",
            EventLogRecord,
            EventLogRecordRawRepository
        )

        await migrate_collection(
            "foresight_records",
            ForesightRecord,
            ForesightRecordRawRepository
        )

        await migrate_collection(
            "conversation_metas",
            ConversationMeta,
            ConversationMetaRawRepository
        )

        print("\n" + "="*80)
        print("✅ 迁移完成！")
        print("="*80)
        print("\n现在可以运行测试脚本验证:")
        print("  uv run python src/bootstrap.py src/tests/test_dual_storage_mongodb_read.py")

    except Exception as e:
        logger.error(f"❌ 迁移过程中出现错误: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
