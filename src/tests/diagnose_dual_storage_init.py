#!/usr/bin/env python3
"""
诊断脚本：检查Repository是否正确初始化了双存储

这个脚本会检查：
1. Repository是否有DualStorageMixin
2. self.model是否被替换为DualStorageModelProxy
3. Document类的方法是否被monkey patched
"""

import sys
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


def diagnose_repository(repo_class, repo_name):
    """诊断单个Repository的双存储状态"""
    print(f"\n{'='*80}")
    print(f"诊断: {repo_name}")
    print(f"{'='*80}")

    try:
        # 获取Repository实例
        repo = get_bean_by_type(repo_class)
        print(f"✅ Repository实例获取成功")

        # 检查1: 是否有DualStorageMixin
        from infra_layer.adapters.out.persistence.kv_storage.dual_storage_mixin import DualStorageMixin
        has_mixin = isinstance(repo, DualStorageMixin)
        print(f"\n1️⃣ DualStorageMixin检查:")
        print(f"   {'✅' if has_mixin else '❌'} 是否有DualStorageMixin: {has_mixin}")

        if not has_mixin:
            print(f"   ⚠️  Repository没有继承DualStorageMixin!")
            print(f"   MRO: {[c.__name__ for c in repo.__class__.__mro__]}")
            return

        # 检查2: self.model类型
        print(f"\n2️⃣ self.model检查:")
        print(f"   类型: {type(repo.model).__name__}")

        from infra_layer.adapters.out.persistence.kv_storage.dual_storage_model_proxy import DualStorageModelProxy
        is_proxy = isinstance(repo.model, DualStorageModelProxy)
        print(f"   {'✅' if is_proxy else '❌'} 是否是DualStorageModelProxy: {is_proxy}")

        if not is_proxy:
            print(f"   ❌ self.model没有被替换为DualStorageModelProxy!")
            print(f"   这意味着DualStorageMixin.__init__没有执行或执行失败")
            return

        # 检查3: Document类的monkey patch
        print(f"\n3️⃣ Document类Monkey Patch检查:")

        # 获取Document类
        original_model = repo.model._original_model
        print(f"   Document类: {original_model.__name__}")

        # 检查是否有_original_insert（说明被monkey patched了）
        has_original_insert = hasattr(original_model, '_original_insert')
        print(f"   {'✅' if has_original_insert else '❌'} 是否有_original_insert: {has_original_insert}")

        if has_original_insert:
            print(f"   ✅ Document类的insert()方法已被monkey patched")
            print(f"   ✅ 双存储应该能正常工作")
        else:
            print(f"   ❌ Document类的insert()方法没有被monkey patched")
            print(f"   ⚠️  这会导致双存储不工作")

        # 检查4: KV-Storage实例
        print(f"\n4️⃣ KV-Storage实例检查:")
        has_kv = hasattr(repo, '_kv_storage') and repo._kv_storage is not None
        print(f"   {'✅' if has_kv else '❌'} 是否有KV-Storage实例: {has_kv}")

        if has_kv:
            print(f"   KV-Storage类型: {type(repo._kv_storage).__name__}")

        # 检查5: indexed_fields
        print(f"\n5️⃣ Indexed Fields检查:")
        if hasattr(repo.model, '_indexed_fields'):
            indexed_fields = repo.model._indexed_fields
            print(f"   ✅ Indexed fields数量: {len(indexed_fields)}")
            print(f"   Fields: {sorted(indexed_fields)}")
        else:
            print(f"   ❌ 没有_indexed_fields")

        print(f"\n{'='*80}")
        print(f"✅ 诊断完成: {repo_name} 双存储配置正确")
        print(f"{'='*80}")

    except Exception as e:
        print(f"❌ 诊断失败: {e}")
        import traceback
        traceback.print_exc()


def main():
    print("\n" + "🔍"*40)
    print("双存储初始化诊断")
    print("🔍"*40)

    from infra_layer.adapters.out.persistence.repository.episodic_memory_raw_repository import (
        EpisodicMemoryRawRepository,
    )
    from infra_layer.adapters.out.persistence.repository.event_log_record_raw_repository import (
        EventLogRecordRawRepository,
    )
    from infra_layer.adapters.out.persistence.repository.foresight_record_repository import (
        ForesightRecordRawRepository,
    )

    # 诊断3个主要的Repository
    diagnose_repository(EpisodicMemoryRawRepository, "EpisodicMemoryRawRepository")
    diagnose_repository(EventLogRecordRawRepository, "EventLogRecordRawRepository")
    diagnose_repository(ForesightRecordRawRepository, "ForesightRecordRawRepository")

    print("\n" + "="*80)
    print("总结")
    print("="*80)
    print("\n如果所有检查都✅，双存储应该能正常工作")
    print("如果有任何❌，说明双存储初始化失败")
    print("\n可能的原因：")
    print("  1. Repository.__init__没有被调用")
    print("  2. DualStorageMixin.__init__执行失败")
    print("  3. KVStorageInterface没有在DI容器中注册")


if __name__ == "__main__":
    main()
