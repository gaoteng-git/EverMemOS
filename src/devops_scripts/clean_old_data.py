#!/usr/bin/env python3
"""
清理旧数据脚本

删除MongoDB中不完整的旧数据（只有Lite字段，没有内容字段）

使用方法：
    uv run python src/bootstrap.py src/devops_scripts/clean_old_data.py
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

from core.observation.logger import get_logger

logger = get_logger(__name__)


async def clean_collection(collection_name: str, model_class):
    """清空单个集合"""
    print(f"\n{'='*80}")
    print(f"清理集合: {collection_name}")
    print(f"{'='*80}")

    mongo_collection = model_class.get_pymongo_collection()
    count = await mongo_collection.count_documents({})

    print(f"  当前文档数: {count}")

    if count == 0:
        print(f"  ℹ️  集合已经是空的")
        return

    # 确认
    print(f"  ⚠️  即将删除 {count} 条文档")

    # 删除
    result = await mongo_collection.delete_many({})
    print(f"  ✅ 已删除 {result.deleted_count} 条文档")


async def main():
    """主清理流程"""
    print("\n" + "🗑️ "*40)
    print("清理MongoDB旧数据")
    print("删除不完整的Lite数据")
    print("🗑️ "*40)

    from infra_layer.adapters.out.persistence.document.memory.episodic_memory import (
        EpisodicMemory,
    )
    from infra_layer.adapters.out.persistence.document.memory.event_log_record import (
        EventLogRecord,
    )
    from infra_layer.adapters.out.persistence.document.memory.foresight_record import (
        ForesightRecord,
    )

    try:
        await clean_collection("episodic_memories", EpisodicMemory)
        await clean_collection("event_log_records", EventLogRecord)
        await clean_collection("foresight_records", ForesightRecord)

        print("\n" + "="*80)
        print("✅ 清理完成！")
        print("="*80)
        print("\n现在可以重新运行demo生成新数据:")
        print("  uv run python src/bootstrap.py demo/simple_demo.py")

    except Exception as e:
        logger.error(f"❌ 清理过程中出现错误: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
