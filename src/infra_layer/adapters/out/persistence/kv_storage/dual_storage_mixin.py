"""
Dual Storage Mixin - Model 层拦截方案

最小侵入方案：通过拦截 self.model 的 MongoDB 调用实现双存储
- Repository 代码零改动（连 append/get_by_id 等方法都不需要改）
- 主分支更新 CRUD 时，无需同步更新
- 双存储完全透明

工作原理：
1. 在 __init__ 中替换 self.model 为 DualStorageModelProxy
2. Proxy 拦截所有 MongoDB 调用（find, get 等）
3. Monkey patch document 类的实例方法（insert, save, delete）
4. 自动处理双存储同步

使用示例：
    class EpisodicMemoryRawRepository(
        DualStorageMixin,  # 只需添加 Mixin
        BaseRepository[EpisodicMemory]
    ):
        # 所有代码完全不变
        pass
"""

from typing import TypeVar, Generic, Type, Optional

from core.observation.logger import get_logger
from infra_layer.adapters.out.persistence.kv_storage.kv_storage_interface import (
    KVStorageInterface,
)
from infra_layer.adapters.out.persistence.kv_storage.dual_storage_model_proxy import (
    DualStorageModelProxy,
    DocumentInstanceWrapper,
)

logger = get_logger(__name__)

TDocument = TypeVar("TDocument")


class DualStorageMixin(Generic[TDocument]):
    """
    Dual Storage Mixin - Model 层拦截实现

    通过拦截 self.model 来自动实现双存储，Repository 代码零改动。

    工作流程：
    1. __init__ 时替换 self.model 为 ModelProxy
    2. Proxy 拦截 find(), get() 等方法
    3. Monkey patch Document 类的 insert(), save(), delete()
    4. 所有 MongoDB 操作自动同步 KV-Storage

    优势：
    - Repository 所有代码完全不需要改动
    - 主分支更新时无需同步更新
    - 双存储逻辑完全透明
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize mixin and setup dual storage interception

        自动：
        1. 获取 KV-Storage 实例
        2. 替换 self.model 为 ModelProxy
        3. Monkey patch Document 实例方法
        """
        super().__init__(*args, **kwargs)

        # 立即初始化双存储（不延迟）
        self._kv_storage: Optional[KVStorageInterface] = None
        self._setup_dual_storage()

    def _setup_dual_storage(self):
        """
        Setup dual storage interception immediately

        在 __init__ 时立即设置拦截
        """
        try:
            # 1. 获取 KV-Storage 实例
            self._kv_storage = self._get_kv_storage()

            # 2. 替换 self.model 为 ModelProxy
            original_model = self.model
            self.model = DualStorageModelProxy(
                original_model=original_model,
                kv_storage=self._kv_storage,
                full_model_class=original_model,
            )

            # 3. Monkey patch Document 类的实例方法
            # 传递 indexed_fields 给 wrapper
            self._patch_document_methods(original_model, self.model._indexed_fields)

            logger.debug(
                f"✅ Dual storage initialized for {original_model.__name__}"
            )

        except Exception as e:
            logger.error(f"❌ Failed to initialize dual storage: {e}")
            raise

    def _get_kv_storage(self) -> KVStorageInterface:
        """Lazy load KV-Storage instance from DI container"""
        if self._kv_storage is None:
            from core.di import get_bean_by_type

            self._kv_storage = get_bean_by_type(KVStorageInterface)
        return self._kv_storage

    def _patch_document_methods(self, document_class, indexed_fields):
        """
        Monkey patch Document 类的实例方法

        Wrap insert(), save(), delete() 以实现 Lite 存储：
        - MongoDB 只存索引字段（Lite）
        - KV-Storage 存完整数据（Full）

        Args:
            document_class: Document model class (e.g., EpisodicMemory)
            indexed_fields: 索引字段集合（运行时自动提取）
        """
        kv_storage = self._kv_storage

        # 保存原始方法
        if not hasattr(document_class, "_original_insert"):
            document_class._original_insert = document_class.insert
            document_class._original_save = document_class.save
            document_class._original_delete = document_class.delete

            # Wrap 实例方法 - 传递 indexed_fields
            document_class.insert = DocumentInstanceWrapper.wrap_insert(
                document_class._original_insert, kv_storage, indexed_fields
            )
            document_class.save = DocumentInstanceWrapper.wrap_save(
                document_class._original_save, kv_storage, indexed_fields
            )
            document_class.delete = DocumentInstanceWrapper.wrap_delete(
                document_class._original_delete, kv_storage
            )

            # Wrap restore() and hard_delete() if they exist (for soft-delete documents)
            if hasattr(document_class, "restore"):
                document_class._original_restore = document_class.restore
                document_class.restore = DocumentInstanceWrapper.wrap_restore(
                    document_class._original_restore, kv_storage
                )

            if hasattr(document_class, "hard_delete"):
                document_class._original_hard_delete = document_class.hard_delete
                document_class.hard_delete = DocumentInstanceWrapper.wrap_hard_delete(
                    document_class._original_hard_delete, kv_storage
                )

            logger.debug(
                f"✅ Patched instance methods for {document_class.__name__} (Lite: {len(indexed_fields)} fields)"
            )


__all__ = ["DualStorageMixin"]
