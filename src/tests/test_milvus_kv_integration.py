#!/usr/bin/env python3
"""
测试 Milvus + KV-Storage 整合功能

本测试验证项目封装的 "先读 Milvus 后读 KV-Storage" 功能是否正确工作。

测试流程:
1. 方法A (手动方式):
   - 直接从 Milvus 读取数据
   - 输出 Milvus 中有值的字段
   - 对每条数据，去 KV-Storage 读取完整数据
   - 输出文本字段是否存在且有值
   - 手动合并数据

2. 方法B (封装方式):
   - 使用项目封装的功能 (MilvusCollectionProxy)
   - 自动从 Milvus 读取后从 KV-Storage 补全数据
   - 返回完整数据

3. 比较 A 和 B:
   - 验证所有字段是否完全相等
   - 验证数据完整性
"""

import sys
import asyncio
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# IMPORTANT: Must setup environment and DI BEFORE importing
from common_utils.load_env import setup_environment
setup_environment(load_env_file_name=".env", check_env_var="MONGODB_HOST")

# Setup all (DI container, etc.)
from application_startup import setup_all
setup_all(load_entrypoints=False)

from core.di import get_bean_by_type
from core.observation.logger import get_logger
from infra_layer.adapters.out.persistence.kv_storage.kv_storage_interface import (
    KVStorageInterface,
)
from infra_layer.adapters.out.search.repository.episodic_memory_milvus_repository import (
    EpisodicMemoryMilvusRepository,
)
from infra_layer.adapters.out.search.milvus.memory.episodic_memory_collection import (
    EpisodicMemoryCollection,
)
from infra_layer.adapters.out.search.repository.event_log_milvus_repository import (
    EventLogMilvusRepository,
)
from infra_layer.adapters.out.search.repository.foresight_milvus_repository import (
    ForesightMilvusRepository,
)

logger = get_logger(__name__)


def print_field_info(title: str, data: Dict[str, Any], indent: str = "  "):
    """打印字段信息 - 显示所有字段，不省略"""
    print(f"\n{indent}{title}:")

    # 分类字段
    text_fields = []
    numeric_fields = []
    list_fields = []
    dict_fields = []
    other_fields = []

    for field_name, field_value in data.items():
        has_value = field_value is not None

        if not has_value:
            continue

        if isinstance(field_value, str):
            text_fields.append((field_name, field_value))
        elif isinstance(field_value, (int, float)):
            numeric_fields.append((field_name, field_value))
        elif isinstance(field_value, list):
            list_fields.append((field_name, field_value))
        elif isinstance(field_value, dict):
            dict_fields.append((field_name, field_value))
        else:
            other_fields.append((field_name, field_value))

    # 打印文本字段 - 显示所有
    if text_fields:
        print(f"{indent}  📝 文本字段 ({len(text_fields)}):")
        for field_name, field_value in text_fields:
            preview = str(field_value)[:50] + "..." if len(str(field_value)) > 50 else str(field_value)
            print(f"{indent}    - {field_name}: '{preview}'")

    # 打印数值字段 - 显示所有
    if numeric_fields:
        print(f"{indent}  🔢 数值字段 ({len(numeric_fields)}):")
        for field_name, field_value in numeric_fields:
            print(f"{indent}    - {field_name}: {field_value}")

    # 打印列表字段 - 显示所有
    if list_fields:
        print(f"{indent}  📋 列表字段 ({len(list_fields)}):")
        for field_name, field_value in list_fields:
            length = len(field_value) if isinstance(field_value, list) else 0
            print(f"{indent}    - {field_name}: [长度: {length}]")

    # 打印字典字段 - 显示所有
    if dict_fields:
        print(f"{indent}  📦 字典字段 ({len(dict_fields)}):")
        for field_name, field_value in dict_fields:
            keys = list(field_value.keys()) if isinstance(field_value, dict) else []
            print(f"{indent}    - {field_name}: {{{len(keys)} keys}}")


def compare_dicts(dict_a: Dict[str, Any], dict_b: Dict[str, Any], path: str = "") -> List[str]:
    """
    深度比较两个字典

    Args:
        dict_a: 字典A
        dict_b: 字典B
        path: 当前路径（用于错误消息）

    Returns:
        差异列表
    """
    differences = []

    # 检查键集合
    keys_a = set(dict_a.keys())
    keys_b = set(dict_b.keys())

    only_in_a = keys_a - keys_b
    only_in_b = keys_b - keys_a

    if only_in_a:
        differences.append(f"{path}: 只在A中: {only_in_a}")
    if only_in_b:
        differences.append(f"{path}: 只在B中: {only_in_b}")

    # 比较共同的键
    common_keys = keys_a & keys_b
    for key in common_keys:
        new_path = f"{path}.{key}" if path else key
        val_a = dict_a[key]
        val_b = dict_b[key]

        # 类型检查
        if type(val_a) != type(val_b):
            differences.append(
                f"{new_path}: 类型不同 (A: {type(val_a).__name__}, B: {type(val_b).__name__})"
            )
            continue

        # 递归比较字典
        if isinstance(val_a, dict):
            differences.extend(compare_dicts(val_a, val_b, new_path))
        # 比较列表
        elif isinstance(val_a, list):
            if len(val_a) != len(val_b):
                differences.append(
                    f"{new_path}: 列表长度不同 (A: {len(val_a)}, B: {len(val_b)})"
                )
            else:
                for i, (item_a, item_b) in enumerate(zip(val_a, val_b)):
                    if isinstance(item_a, dict) and isinstance(item_b, dict):
                        differences.extend(compare_dicts(item_a, item_b, f"{new_path}[{i}]"))
                    elif item_a != item_b:
                        differences.append(f"{new_path}[{i}]: 值不同")
        # 比较其他类型
        else:
            if val_a != val_b:
                differences.append(
                    f"{new_path}: 值不同 (A: {val_a}, B: {val_b})"
                )

    return differences


async def method_a_manual_read(
    milvus_repo,  # 可以是任何 Milvus Repository
    kv_storage: KVStorageInterface,
    limit: int = 5,
    collection_name: str = "episodic_memory"
) -> List[Dict[str, Any]]:
    """
    方法A: 手动方式

    1. 直接从 Milvus 读取数据（使用原始 collection，绕过 Proxy）
    2. 对每条数据，手动从 KV-Storage 读取完整数据
    3. 手动合并数据

    Args:
        milvus_repo: Milvus Repository 实例
        kv_storage: KV-Storage 实例
        limit: 查询数量限制
        collection_name: Collection 名称（用于构造 KV key）
    """
    print("\n" + "="*80)
    print("方法A: 手动读取 Milvus + KV-Storage")
    print("="*80)

    results = []

    # 获取原始的 AsyncCollection (绕过 Proxy)
    if hasattr(milvus_repo.collection, '_original_collection'):
        # 如果是 Proxy，获取原始 collection
        original_collection = milvus_repo.collection._original_collection
        print("✅ 获取到原始 AsyncCollection (绕过 Proxy)")
    else:
        # 直接使用 collection
        original_collection = milvus_repo.collection
        print("⚠️  直接使用 collection (可能已经是 Proxy)")

    # 从 Milvus 查询数据（只获取 Lite 字段）
    print(f"\n📥 步骤1: 从 Milvus 查询前 {limit} 条数据...")
    milvus_results = await original_collection.query(
        expr="",  # 查询所有
        output_fields=["*"],  # 获取所有字段
        limit=limit,
    )

    print(f"   找到 {len(milvus_results)} 条记录")

    # 处理每条数据
    for idx, milvus_data in enumerate(milvus_results, 1):
        doc_id = milvus_data.get("id")

        print(f"\n  📄 记录 {idx}/{len(milvus_results)}: ID = {doc_id}")

        # 打印 Milvus 中的字段
        print_field_info("Milvus 数据", milvus_data, "    ")

        # 从 KV-Storage 读取完整数据
        print(f"\n    📥 步骤2: 从 KV-Storage 读取完整数据...")
        kv_key = f"milvus:{collection_name}:{doc_id}"
        kv_value = await kv_storage.get(kv_key)

        if kv_value:
            print(f"    ✅ KV-Storage 中找到数据 ({len(kv_value)} bytes)")
            full_data = json.loads(kv_value)

            # 打印 KV 中的文本字段
            print_field_info("KV-Storage 完整数据", full_data, "    ")

            # 手动合并数据（KV 数据覆盖 Milvus Lite 数据）
            merged_data = {**milvus_data, **full_data}

            print(f"    ✅ 合并完成，共 {len(merged_data)} 个字段")
            results.append(merged_data)
        else:
            print(f"    ❌ KV-Storage 中未找到数据")
            # 只有 Milvus Lite 数据
            results.append(milvus_data)

    print(f"\n✅ 方法A 完成: 返回 {len(results)} 条完整数据")
    return results


async def method_b_encapsulated_read(
    milvus_repo,  # 可以是任何 Milvus Repository
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    方法B: 使用项目封装的功能

    使用 MilvusCollectionProxy，它会自动：
    1. 从 Milvus 读取 Lite 数据
    2. 批量从 KV-Storage 加载完整数据
    3. 自动合并并返回

    Args:
        milvus_repo: Milvus Repository 实例
        limit: 查询数量限制
    """
    print("\n" + "="*80)
    print("方法B: 使用封装功能 (MilvusCollectionProxy)")
    print("="*80)

    # 通过 Proxy 查询（会自动从 KV 加载完整数据）
    print(f"\n📥 使用 collection.query() (自动从 KV 补全数据)...")
    results = await milvus_repo.collection.query(
        expr="",  # 查询所有
        output_fields=["*"],  # 获取所有字段
        limit=limit,
    )

    print(f"   返回 {len(results)} 条记录")

    # 打印每条数据的信息
    for idx, data in enumerate(results, 1):
        doc_id = data.get("id")
        print(f"\n  📄 记录 {idx}/{len(results)}: ID = {doc_id}")
        print_field_info("封装方法返回的数据", data, "    ")

    print(f"\n✅ 方法B 完成: 返回 {len(results)} 条完整数据")
    return results


def check_important_text_fields(data: Dict[str, Any]) -> Dict[str, bool]:
    """
    检查重要的文本字段是否存在且有值

    重要字段包括 Milvus 中存储的完整内容字段（非 Lite 字段）
    不同集合有不同的重要字段：
    - episodic_memory: title, summary, subject, episode
    - event_log: atomic_fact
    - foresight: content, evidence
    """
    # 定义重要的文本字段（这些是应该从 KV-Storage 加载的完整内容字段）
    important_fields = {
        # Episodic Memory 的重要字段
        "title",           # 标题
        "summary",         # 摘要
        "subject",         # 主题
        "user_name",       # 用户名
        "keywords",        # 关键词
        "linked_entities", # 关联实体
        "episode",         # episode 描述
        # Event Log 的重要字段
        "atomic_fact",     # 原子事实
        # Foresight 的重要字段
        "content",         # 内容
        "evidence",        # 证据
    }

    found_fields = {}

    # 检查直接字段
    for field in important_fields:
        value = data.get(field)
        has_value = value is not None and value != "" and value != []
        found_fields[field] = has_value

    # 特别检查 metadata 字段（JSON 字符串）
    metadata_str = data.get("metadata", "")
    if metadata_str:
        try:
            import json
            metadata = json.loads(metadata_str)
            # 检查 metadata 中的字段
            for field in ["title", "summary", "subject", "user_name", "keywords", "linked_entities"]:
                if field in metadata:
                    value = metadata[field]
                    has_value = value is not None and value != "" and value != []
                    found_fields[field] = found_fields.get(field, False) or has_value
        except:
            pass

    return found_fields


async def compare_results(results_a: List[Dict[str, Any]], results_b: List[Dict[str, Any]]):
    """
    比较方法A和方法B的结果
    """
    print("\n" + "="*80)
    print("结果比较: 方法A vs 方法B")
    print("="*80)

    # 检查数量
    print(f"\n📊 数据数量比较:")
    print(f"  方法A: {len(results_a)} 条")
    print(f"  方法B: {len(results_b)} 条")

    if len(results_a) != len(results_b):
        print(f"  ❌ FAIL: 数量不同!")
        return False

    print(f"  ✅ 数量相同")

    # 检查是否有重要文本字段
    print(f"\n🔍 检查重要文本字段 (来自 KV-Storage 的完整数据):")

    has_important_fields_a = False
    has_important_fields_b = False

    for idx, (data_a, data_b) in enumerate(zip(results_a, results_b), 1):
        fields_a = check_important_text_fields(data_a)
        fields_b = check_important_text_fields(data_b)

        found_in_a = [k for k, v in fields_a.items() if v]
        found_in_b = [k for k, v in fields_b.items() if v]

        if found_in_a:
            has_important_fields_a = True
            print(f"  记录 {idx} - 方法A 找到: {', '.join(found_in_a)}")
        if found_in_b:
            has_important_fields_b = True
            print(f"  记录 {idx} - 方法B 找到: {', '.join(found_in_b)}")

    # 如果两个方法都没有找到重要字段，说明 KV-Storage 中没有数据
    if not has_important_fields_a and not has_important_fields_b:
        print("\n" + "⚠️ " * 40)
        print("⚠️  警告: 未检测到重要的文本字段!")
        print("⚠️ " * 40)
        print("\n原因分析:")
        print("  1. KV-Storage 中没有完整数据")
        print("  2. 数据可能是在 Milvus 双存储功能启用前创建的")
        print("  3. 或者数据同步到 Milvus 时未同时写入 KV-Storage")
        print("\n建议:")
        print("  1. 重新运行 demo 创建新数据:")
        print("     uv run python src/bootstrap.py demo/simple_demo.py")
        print("  2. 等待 30 秒让数据处理完成")
        print("  3. 重新运行此测试")
        print("\n" + "⚠️ " * 40)
        print("\n❌ 测试失败: 未能验证 KV-Storage 完整数据加载功能")
        print("   只测试了 Lite 数据，无法验证双存储的完整性")
        print("="*80)
        return False

    print(f"\n  ✅ 检测到重要文本字段")
    if has_important_fields_a:
        print(f"     方法A: 有完整数据")
    if has_important_fields_b:
        print(f"     方法B: 有完整数据")

    # 逐条比较
    all_match = True
    for idx, (data_a, data_b) in enumerate(zip(results_a, results_b), 1):
        doc_id_a = data_a.get("id")
        doc_id_b = data_b.get("id")

        print(f"\n  📄 记录 {idx}: ID = {doc_id_a}")

        # 比较 ID
        if doc_id_a != doc_id_b:
            print(f"    ❌ FAIL: ID 不同 (A: {doc_id_a}, B: {doc_id_b})")
            all_match = False
            continue

        # 深度比较字段
        differences = compare_dicts(data_a, data_b, f"Record[{idx}]")

        if differences:
            print(f"    ❌ FAIL: 发现 {len(differences)} 处差异:")
            for diff in differences[:10]:  # 只显示前10个差异
                print(f"      - {diff}")
            if len(differences) > 10:
                print(f"      ... 还有 {len(differences) - 10} 处差异")
            all_match = False
        else:
            print(f"    ✅ PASS: 所有字段完全相同")

    # 总结
    print("\n" + "="*80)
    if all_match:
        print("🎉 ✅ 测试通过: 方法A 和 方法B 返回的数据完全相同!")
        print("   → MilvusCollectionProxy 正确工作")
        print("   → 自动从 KV-Storage 加载完整数据功能正常")
        print("   → 完整文本字段验证通过")
    else:
        print("❌ 测试失败: 方法A 和 方法B 返回的数据不同!")
        print("   → 需要检查 MilvusCollectionProxy 的实现")
    print("="*80)

    return all_match


async def test_episodic_memory_integration(kv_storage: KVStorageInterface, test_limit: int = 5) -> bool:
    """测试 Episodic Memory 的 Milvus + KV-Storage 整合"""
    print("\n" + "=" * 80)
    print("📊 测试集合: Episodic Memory")
    print("=" * 80)

    milvus_repo = get_bean_by_type(EpisodicMemoryMilvusRepository)

    print(f"\n✅ Repository 初始化完成:")
    print(f"  - Repository: {type(milvus_repo).__name__}")
    print(f"  - Collection Proxy: {type(milvus_repo.collection).__name__}")

    # 方法A: 手动读取
    results_a = await method_a_manual_read(
        milvus_repo, kv_storage, limit=test_limit, collection_name="episodic_memory"
    )

    # 方法B: 使用封装功能
    results_b = await method_b_encapsulated_read(milvus_repo, limit=test_limit)

    # 比较结果
    success = await compare_results(results_a, results_b)

    return success


async def test_event_log_integration(kv_storage: KVStorageInterface, test_limit: int = 5) -> bool:
    """测试 Event Log 的 Milvus + KV-Storage 整合"""
    print("\n" + "=" * 80)
    print("📊 测试集合: Event Log")
    print("=" * 80)

    milvus_repo = get_bean_by_type(EventLogMilvusRepository)

    print(f"\n✅ Repository 初始化完成:")
    print(f"  - Repository: {type(milvus_repo).__name__}")
    print(f"  - Collection Proxy: {type(milvus_repo.collection).__name__}")

    # 方法A: 手动读取
    results_a = await method_a_manual_read(
        milvus_repo, kv_storage, limit=test_limit, collection_name="event_log"
    )

    # 方法B: 使用封装功能
    results_b = await method_b_encapsulated_read(milvus_repo, limit=test_limit)

    # 比较结果
    success = await compare_results(results_a, results_b)

    return success


async def test_foresight_integration(kv_storage: KVStorageInterface, test_limit: int = 5) -> bool:
    """测试 Foresight 的 Milvus + KV-Storage 整合"""
    print("\n" + "=" * 80)
    print("📊 测试集合: Foresight")
    print("=" * 80)

    milvus_repo = get_bean_by_type(ForesightMilvusRepository)

    print(f"\n✅ Repository 初始化完成:")
    print(f"  - Repository: {type(milvus_repo).__name__}")
    print(f"  - Collection Proxy: {type(milvus_repo.collection).__name__}")

    # 方法A: 手动读取
    results_a = await method_a_manual_read(
        milvus_repo, kv_storage, limit=test_limit, collection_name="foresight"
    )

    # 方法B: 使用封装功能
    results_b = await method_b_encapsulated_read(milvus_repo, limit=test_limit)

    # 比较结果
    success = await compare_results(results_a, results_b)

    return success


async def main():
    """主测试函数"""
    print("\n" + "🧪" * 40)
    print("Milvus + KV-Storage 整合测试")
    print("验证项目封装的自动数据加载功能")
    print("测试集合: Episodic Memory, Event Log, Foresight")
    print("🧪" * 40)

    try:
        # 获取 KV-Storage
        kv_storage = get_bean_by_type(KVStorageInterface)

        print(f"\n✅ KV-Storage 初始化完成: {type(kv_storage).__name__}")

        # 设置测试数量
        test_limit = 5

        # 测试结果列表
        all_results = []

        # 测试1: Episodic Memory
        print("\n" + "🔬" * 40)
        print("测试 1/3: Episodic Memory")
        print("🔬" * 40)
        success_episodic = await test_episodic_memory_integration(kv_storage, test_limit)
        all_results.append(("Episodic Memory", success_episodic))

        # 测试2: Event Log
        print("\n" + "🔬" * 40)
        print("测试 2/3: Event Log")
        print("🔬" * 40)
        success_event_log = await test_event_log_integration(kv_storage, test_limit)
        all_results.append(("Event Log", success_event_log))

        # 测试3: Foresight
        print("\n" + "🔬" * 40)
        print("测试 3/3: Foresight")
        print("🔬" * 40)
        success_foresight = await test_foresight_integration(kv_storage, test_limit)
        all_results.append(("Foresight", success_foresight))

        # 总结
        print("\n" + "=" * 80)
        print("🎯 测试总结")
        print("=" * 80)

        passed = sum(1 for _, success in all_results if success)
        total = len(all_results)

        for collection_name, success in all_results:
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"  {status}: {collection_name}")

        print(f"\n总计: {passed}/{total} 通过")

        if passed == total:
            print("\n🎉 所有测试通过!")
            return 0
        else:
            print(f"\n⚠️  {total - passed} 个测试失败")
            return 1

    except Exception as e:
        logger.error(f"❌ 测试过程中出现错误: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
