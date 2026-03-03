# Dual Storage Architecture - 双存储架构详解

## 目录

1. [架构概述](#架构概述)
2. [核心组件](#核心组件)
3. [初始化流程](#初始化流程)
4. [CRUD 操作详解](#crud-操作详解)
5. [Lite 数据构建](#lite-数据构建)
6. [数据流图](#数据流图)
7. [FAQ](#faq)

---

## 架构概述

双存储架构通过**零侵入**的方式，在 Repository 层自动实现：
- **MongoDB**：存储 Lite 数据（仅索引字段 + query_fields）
- **KV-Storage**：存储完整数据（Full Data）

### 核心理念

```
┌─────────────────────────────────────────────────────────┐
│               Repository (零代码改动)                      │
│  class MemCellRawRepository(                             │
│      DualStorageMixin,  # ← 仅添加这一行                  │
│      BaseRepository[MemCell]                             │
│  ): pass                                                 │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│            DualStorageMixin (透明拦截层)                  │
│  • 替换 self.model 为 DualStorageModelProxy              │
│  • Monkey Patch Document 实例方法                        │
│  • 自动同步 MongoDB ↔ KV-Storage                         │
└─────────────────────────────────────────────────────────┘
                           ↓
        ┌──────────────────────────────────┐
        │   DualStorageModelProxy          │
        │  (拦截类级别方法)                  │
        │   • find()                       │
        │   • find_one()                   │
        │   • update_many()                │
        │   • delete_all()                 │
        └──────────────────────────────────┘
                           ↓
┌───────────────────────┐    ┌────────────────────────┐
│   MongoDB (Lite)      │    │   KV-Storage (Full)    │
│   • 索引字段           │    │   • 完整数据            │
│   • query_fields      │    │   • JSON 格式          │
│   • 高速查询           │    │   • 可恢复             │
└───────────────────────┘    └────────────────────────┘
```

---

## 核心组件

### 1. DualStorageMixin

**文件**: `dual_storage_mixin.py`

**作用**: Repository 初始化时的拦截入口

```python
class DualStorageMixin(Generic[TDocument]):
    """
    双存储 Mixin - Repository 零代码改动的秘密

    工作流程：
    1. 在 __init__ 时拦截并替换 self.model
    2. 将原始 Beanie Document 类包装为 DualStorageModelProxy
    3. Monkey Patch Document 实例方法 (insert, save, delete)
    """

    def __init__(self, *args, **kwargs):
        # 调用父类（BaseRepository）的 __init__
        # BaseRepository 会设置 self.model = MemCell
        super().__init__(*args, **kwargs)

        # 核心操作：替换 self.model
        original_model = self.model  # 此时 self.model 已被 BaseRepository 设置
        self.model = DualStorageModelProxy(
            original_model=original_model,
            kv_storage=self._kv_storage,
            full_model_class=original_model,  # ← 使用 original_model（即 MemCell）
        )

        # Monkey Patch 实例方法
        self._patch_document_methods(original_model, self.model._indexed_fields)
```

**关键点**:
- ✅ Repository 代码**零改动**（只添加 Mixin 继承）
- ✅ 透明拦截，对业务代码完全透明
- ✅ 支持所有 Beanie 操作

### 2. DualStorageModelProxy

**文件**: `dual_storage_model_proxy.py`

**作用**: 拦截类级别的 MongoDB 操作（find, find_one, update_many 等）

```python
class DualStorageModelProxy:
    """
    Model 代理 - 拦截类级别方法

    拦截的方法：
    - find()       → 返回 DualStorageQueryProxy
    - find_one()   → 返回 FindOneQueryProxy
    - update_many() → 批量更新 + KV 同步
    - delete_all() → 批量删除 + KV 同步
    """

    def __init__(self, original_model, kv_storage, full_model_class):
        self._original_model = original_model      # 原始 Beanie Document 类
        self._kv_storage = kv_storage              # KV 存储实例
        self._full_model_class = full_model_class  # 完整 Document 类
        self._indexed_fields = self._extract_indexed_fields()

    def find(self, *args, **kwargs):
        """拦截 find() - 返回支持链式调用的 QueryProxy"""
        return DualStorageQueryProxy(
            original_query=self._original_model.find(*args, **kwargs),
            kv_storage=self._kv_storage,
            full_model_class=self._full_model_class,
        )

    def find_one(self, *args, **kwargs):
        """拦截 find_one() - 返回支持 .delete() 链式调用的 Proxy"""
        return FindOneQueryProxy(
            original_model=self._original_model,
            kv_storage=self._kv_storage,
            full_model_class=self._full_model_class,
            filter_args=args,
            filter_kwargs=kwargs,
        )
```

**关键点**:
- ✅ 拦截所有类级别方法调用
- ✅ 自动验证查询字段是否在 Lite 数据中
- ✅ 从 KV 加载完整数据
- ✅ 支持链式调用（如 `.sort().limit().to_list()`）

### 3. LiteModelExtractor

**文件**: `lite_model_extractor.py`

**作用**: 从完整 Document 提取 Lite 数据（仅索引字段）

```python
class LiteModelExtractor:
    """
    Lite 数据提取器 - 智能提取索引字段

    提取策略：
    1. 自动识别 Indexed 字段（如 Indexed(str)）
    2. 包含 Settings.query_fields（手动指定的查询字段）
    3. 始终包含 _id, created_at, updated_at 等核心字段
    """

    @staticmethod
    def extract_indexed_fields(document_class) -> Set[str]:
        """提取所有索引字段名"""
        indexed_fields = {"id", "created_at", "updated_at", "deleted_at"}

        # 从类型注解提取 Indexed 字段
        for field_name, field_info in document_class.model_fields.items():
            if "Indexed" in str(field_info.annotation):
                indexed_fields.add(field_name)

        # 从 Settings.indexes 提取复合索引字段
        settings = getattr(document_class, "Settings", None)
        if settings and hasattr(settings, "indexes"):
            for index_model in settings.indexes:
                for field_name, _ in index_model.document["key"]:
                    indexed_fields.add(field_name)

        # 添加 query_fields（手动指定）
        if settings and hasattr(settings, "query_fields"):
            indexed_fields.update(settings.query_fields)

        return indexed_fields

    @staticmethod
    def extract_lite_data(document) -> Dict[str, Any]:
        """从完整 Document 提取 Lite 数据"""
        indexed_fields = LiteModelExtractor.extract_indexed_fields(type(document))

        # 排除 ExpressionField（Beanie 内部字段）
        full_data = document.model_dump(
            mode="python",
            exclude={'_id', 'id', 'revision_id'}
        )

        # 仅保留索引字段
        lite_data = {
            field: value
            for field, value in full_data.items()
            if field in indexed_fields
        }

        return lite_data
```

**关键点**:
- ✅ 自动识别索引字段（无需手动配置）
- ✅ 支持 `query_fields` 扩展
- ✅ 排除 Beanie 内部字段

---

## 初始化流程

以 `MemCellRawRepository` 为例，详细说明初始化过程：

### 步骤 1: Repository 初始化

```python
@repository("memcell_raw_repository", primary=True)
class MemCellRawRepository(
    DualStorageMixin,  # ← 第一步：继承 Mixin
    BaseRepository[MemCell],
):
    def __init__(self):
        super().__init__(MemCell)  # ← 第二步：调用父类 __init__
```

**时序图**:

```
Repository.__init__(self)
    ↓
super().__init__(MemCell)  # 传入 MemCell
    ↓
DualStorageMixin.__init__(self, MemCell)
    ↓ super().__init__(MemCell)
    ↓
BaseRepository.__init__(self, MemCell)
    ├─ self.model = MemCell  # 设置 self.model
    └─ 返回到 DualStorageMixin
    ↓
DualStorageMixin._setup_dual_storage():
    ├─ self._kv_storage = self._get_kv_storage()  # 获取 KV-Storage 实例
    ├─ original_model = self.model  # 保存原始 Model（MemCell）
    ├─ self.model = DualStorageModelProxy(
    │      original_model=original_model,  # MemCell 类
    │      kv_storage=self._kv_storage,
    │      full_model_class=original_model  # MemCell 类（与 original_model 相同）
    │  )
    └─ self._patch_document_methods(original_model, indexed_fields)
        # Monkey Patch MemCell 实例方法
```

### 步骤 2: Model 代理创建

```python
class DualStorageModelProxy:
    def __init__(self, original_model, kv_storage, full_model_class):
        self._original_model = original_model      # MemCell 类
        self._kv_storage = kv_storage              # InMemoryKVStorage 实例
        self._full_model_class = full_model_class  # MemCell 类

        # 提取索引字段
        self._indexed_fields = LiteModelExtractor.extract_indexed_fields(
            full_model_class
        )
        # MemCell 的索引字段：
        # {'id', 'user_id', 'timestamp', 'group_id', 'created_at',
        #  'updated_at', 'deleted_at', 'deleted_by'}
```

### 步骤 3: Monkey Patch 实例方法

```python
self._patch_document_methods(original_model, self.model._indexed_fields)
```

**Patch 的方法**:
- `insert()` → `wrap_insert()` - 插入时同步 KV
- `save()` → `wrap_save()` - 保存时同步 KV
- `delete()` → `wrap_delete()` - 删除时同步 KV
- `restore()` → `wrap_restore()` - 恢复时同步 KV（如果存在）
- `hard_delete()` → `wrap_hard_delete()` - 硬删除时同步 KV（如果存在）

**Monkey Patch 原理**:

```python
def _patch_document_methods(self, document_class, indexed_fields):
    """Monkey Patch Document 类的实例方法"""
    kv_storage = self._kv_storage

    # 保存原始方法（仅首次 patch）
    if not hasattr(document_class, "_original_insert"):
        document_class._original_insert = document_class.insert
        document_class._original_save = document_class.save
        document_class._original_delete = document_class.delete

        # 替换为包装方法（传入 indexed_fields）
        document_class.insert = DocumentInstanceWrapper.wrap_insert(
            document_class._original_insert, kv_storage, indexed_fields
        )
        document_class.save = DocumentInstanceWrapper.wrap_save(
            document_class._original_save, kv_storage, indexed_fields
        )
        document_class.delete = DocumentInstanceWrapper.wrap_delete(
            document_class._original_delete, kv_storage
        )
```

**初始化完成后的状态**:

```
MemCellRawRepository 实例
    ├─ self.model = DualStorageModelProxy(MemCell)
    │   ├─ _original_model = MemCell
    │   ├─ _kv_storage = InMemoryKVStorage()
    │   ├─ _full_model_class = MemCell
    │   └─ _indexed_fields = {索引字段集合}
    │
    └─ MemCell 类（已被 Monkey Patch）
        ├─ insert()  → wrap_insert()
        ├─ save()    → wrap_save()
        └─ delete()  → wrap_delete()
```

---

## CRUD 操作详解

### 1. INSERT 操作

#### 1.1 调用入口

```python
# Repository 代码
async def append_memcell(self, memcell: MemCell) -> Optional[MemCell]:
    await memcell.insert()  # ← 实际调用的是 wrap_insert()
    return memcell
```

#### 1.2 执行流程

```
用户代码: memcell.insert()
    ↓
Monkey Patch 拦截
    ↓
wrap_insert(original_insert, kv_storage, MemCell)
    ├─ 步骤 1: 提取 Lite 数据
    │   lite_data = LiteModelExtractor.extract_lite_data(memcell)
    │   # 结果示例：
    │   # {
    │   #   'user_id': 'user123',
    │   #   'timestamp': datetime(...),
    │   #   'group_id': 'group456',
    │   #   'created_at': datetime(...),
    │   # }
    │
    ├─ 步骤 2: 创建 Lite Document
    │   lite_doc = MemCell(**lite_data)
    │
    ├─ 步骤 3: 插入 MongoDB (仅 Lite 数据)
    │   await original_insert(lite_doc)
    │   doc_id = str(lite_doc.id)  # 获取生成的 ID
    │
    ├─ 步骤 4: 序列化完整数据
    │   full_data = memcell.model_dump(mode="python", exclude={'_id', 'revision_id'})
    │   full_data['id'] = doc_id  # 使用相同的 ID
    │   kv_value = json.dumps(full_data, default=json_serializer)
    │
    └─ 步骤 5: 存入 KV-Storage
        await kv_storage.put(key=doc_id, value=kv_value)
        # KV 中存储的是完整 JSON 数据
```

#### 1.3 数据对比

**MongoDB 中存储的 Lite 数据**:
```json
{
  "_id": ObjectId("507f1f77bcf86cd799439011"),
  "user_id": "user123",
  "timestamp": ISODate("2024-01-20T10:30:00Z"),
  "group_id": "group456",
  "created_at": ISODate("2024-01-20T10:30:00Z"),
  "updated_at": ISODate("2024-01-20T10:30:00Z")
}
```

**KV-Storage 中存储的 Full 数据**:
```json
{
  "id": "507f1f77bcf86cd799439011",
  "user_id": "user123",
  "timestamp": "2024-01-20T10:30:00Z",
  "group_id": "group456",
  "summary": "讨论了新功能的设计方案",
  "original_data": [...],  // 完整的原始数据
  "tags": ["meeting", "design"],
  "keywords": ["功能", "设计", "方案"],
  "participants": ["user123", "user456"],
  "raw_data": {...},  // 详细的原始数据结构
  "created_at": "2024-01-20T10:30:00Z",
  "updated_at": "2024-01-20T10:30:00Z"
}
```

**关键差异**:
- MongoDB：仅 6 个索引字段（约 200 bytes）
- KV-Storage：完整数据（约 5KB）
- 压缩比：**约 25:1**

---

### 2. FIND 操作

#### 2.1 调用入口

```python
# Repository 代码
async def find_by_user_id(self, user_id: str, limit: int = 10):
    query = self.model.find({"user_id": user_id})  # ← 被 Proxy 拦截
    results = await query.sort("-timestamp").limit(limit).to_list()
    return results
```

#### 2.2 执行流程

```
用户代码: self.model.find({"user_id": user_id})
    ↓
DualStorageModelProxy.find() 拦截
    ↓
返回 DualStorageQueryProxy
    ├─ _original_query = MemCell.find({"user_id": user_id})
    ├─ _kv_storage = kv_storage
    └─ _full_model_class = MemCell
    ↓
链式调用: .sort("-timestamp").limit(10)
    ├─ sort() 返回 self（支持链式）
    └─ limit() 返回 self（支持链式）
    ↓
终端调用: .to_list()
    ├─ 步骤 1: 执行 MongoDB 查询（仅获取 ID）
    │   lite_results = await _original_query
    │       .project(IdOnlyProjection)  # 仅投影 id 字段
    │       .sort("-timestamp")
    │       .limit(10)
    │       .to_list()
    │   # 结果：[IdOnlyProjection(id="507f..."), ...]
    │
    ├─ 步骤 2: 批量从 KV 加载完整数据
    │   doc_ids = [str(doc.id) for doc in lite_results]
    │   kv_values = await kv_storage.batch_get(keys=doc_ids)
    │
    └─ 步骤 3: 反序列化为 Document 对象
        full_results = [
            MemCell.model_validate_json(kv_value)
            for kv_value in kv_values
        ]
        return full_results
```

#### 2.3 性能优化

**查询字段验证**:
```python
def _validate_query_fields(self, filter_dict):
    """验证查询字段是否在 Lite 数据中"""
    queried_fields = self._extract_query_fields(filter_dict)
    missing_fields = queried_fields - self._indexed_fields

    if missing_fields:
        raise LiteStorageQueryError(
            f"Query uses non-indexed fields: {missing_fields}\n"
            f"Add to Settings.query_fields: {list(missing_fields)}"
        )
```

**示例**:
```python
# ✅ 正确：查询索引字段
await self.model.find({"user_id": "user123"}).to_list()

# ❌ 错误：查询非索引字段
await self.model.find({"summary": "会议"}).to_list()
# 抛出 LiteStorageQueryError:
# Query uses non-indexed fields: {'summary'}
# Add to Settings.query_fields: ['summary']
```

---

### 3. FIND_ONE 操作

#### 3.1 调用入口

```python
# Repository 代码
async def get_by_event_id(self, event_id: str):
    result = await self.model.find_one({"_id": ObjectId(event_id)})
    return result
```

#### 3.2 执行流程

```
用户代码: await self.model.find_one({"_id": ObjectId(event_id)})
    ↓
DualStorageModelProxy.find_one() 拦截
    ↓
返回 FindOneQueryProxy (可 await，支持 .delete())
    ├─ _original_model = MemCell
    ├─ _kv_storage = kv_storage
    └─ _filter_args = ({"_id": ObjectId(...)},)
    ↓
await FindOneQueryProxy
    ├─ 步骤 1: 查询 MongoDB（仅获取 ID）
    │   lite_doc = await MemCell.find_one(
    │       {"_id": ObjectId(event_id)},
    │       projection_model=IdOnlyProjection
    │   )
    │
    ├─ 步骤 2: 从 KV 加载完整数据
    │   doc_id = str(lite_doc.id)
    │   kv_value = await kv_storage.get(key=doc_id)
    │
    └─ 步骤 3: 反序列化
        if kv_value:
            full_doc = MemCell.model_validate_json(kv_value)
            return full_doc
        else:
            logger.warning("KV miss for doc_id")
            return None
```

#### 3.3 特殊场景：支持链式 .delete()

```python
# Repository 代码
async def delete_by_group_id(self, group_id: str):
    result = await self.model.find_one({"group_id": group_id}).delete()
    #                                   ↑ FindOneQueryProxy    ↑ 链式调用
    return result.deleted_count > 0
```

**FindOneQueryProxy.delete() 实现**:
```python
async def delete(self):
    # 1. 获取文档 ID
    lite_doc = await self._original_model.find_one(
        *self._filter_args,
        projection_model=IdOnlyProjection,
        **self._filter_kwargs
    )

    if not lite_doc:
        return DeleteResult(deleted_count=0)

    doc_id = str(lite_doc.id)

    # 2. 删除 MongoDB
    delete_result = await self._original_model.find(
        {"_id": ObjectId(doc_id)}
    ).delete()

    # 3. 删除 KV-Storage
    if delete_result.deleted_count > 0:
        await self._kv_storage.delete(key=doc_id)

    return delete_result
```

---

### 4. UPDATE/SAVE 操作

#### 4.1 调用入口

```python
# Repository 代码
async def update_by_event_id(self, event_id: str, update_data: Dict):
    memcell = await self.get_by_event_id(event_id)
    for key, value in update_data.items():
        setattr(memcell, key, value)
    await memcell.save()  # ← 实际调用的是 wrap_save()
    return memcell
```

#### 4.2 执行流程

```
用户代码: memcell.save()
    ↓
Monkey Patch 拦截
    ↓
wrap_save(original_save, kv_storage, MemCell)
    ├─ 步骤 1: 提取 Lite 数据
    │   lite_data = LiteModelExtractor.extract_lite_data(memcell)
    │
    ├─ 步骤 2: 更新 MongoDB（仅 Lite 字段）
    │   # 方式 1: 使用 update_one 更新部分字段
    │   await collection.update_one(
    │       {"_id": ObjectId(memcell.id)},
    │       {"$set": lite_data}
    │   )
    │
    │   # 方式 2: 调用原始 save()
    │   lite_doc = MemCell(**lite_data)
    │   lite_doc.id = memcell.id
    │   await original_save(lite_doc)
    │
    ├─ 步骤 3: 序列化完整数据
    │   full_data = memcell.model_dump(mode="python")
    │   kv_value = json.dumps(full_data, default=json_serializer)
    │
    └─ 步骤 4: 更新 KV-Storage
        await kv_storage.put(key=str(memcell.id), value=kv_value)
```

#### 4.3 批量更新（update_many）

```python
# Repository 代码
async def confirm_accumulation_by_group_id(self, group_id: str):
    result = await self.model.update_many(
        {"group_id": group_id, "sync_status": -1},
        {"$set": {"sync_status": 0}}
    )
    return result.modified_count
```

**DualStorageModelProxy.update_many() 实现**:
```python
async def update_many(self, filter_query, update_data, **kwargs):
    # 1. 查询所有匹配文档（获取 ID）
    docs = await self.find(filter_query).to_list()
    doc_ids = [str(doc.id) for doc in docs]

    # 2. 批量更新 MongoDB
    collection = self._original_model.get_pymongo_collection()
    result = await collection.update_many(filter_query, update_data)

    # 3. 批量更新 KV-Storage
    if result.modified_count > 0:
        update_fields = update_data.get("$set", {})

        for doc_id in doc_ids:
            kv_value = await self._kv_storage.get(key=doc_id)
            if kv_value:
                full_data = json.loads(kv_value)
                full_data.update(update_fields)  # 应用更新
                await self._kv_storage.put(
                    key=doc_id,
                    value=json.dumps(full_data)
                )

    return result
```

---

### 5. DELETE 操作

#### 5.1 软删除

```python
# Repository 代码
async def delete_by_event_id(self, event_id: str):
    memcell = await self.get_by_event_id(event_id)
    await memcell.delete()  # ← 软删除，实际调用 wrap_delete()
    return True
```

**wrap_delete() 实现**:
```python
async def wrap_delete(original_delete, kv_storage, full_model_class):
    async def _delete(self, *args, **kwargs):
        # 1. 检测是软删除还是硬删除
        is_soft_delete = hasattr(self, 'deleted_at')

        # 2. 执行 MongoDB 删除
        await original_delete(self, *args, **kwargs)

        # 3. 同步 KV-Storage
        if is_soft_delete:
            # 软删除：更新 KV 中的 deleted_at 字段
            full_data = self.model_dump(mode="python")
            kv_value = json.dumps(full_data)
            await kv_storage.put(key=str(self.id), value=kv_value)
        else:
            # 硬删除：从 KV 删除
            await kv_storage.delete(key=str(self.id))

        return self

    return _delete
```

**软删除 vs 硬删除**:

| 操作 | MongoDB | KV-Storage | 可恢复 |
|------|---------|-----------|--------|
| 软删除 `delete()` | 标记 `deleted_at` | 更新 `deleted_at` | ✅ 可恢复 |
| 硬删除 `hard_delete()` | 物理删除 | 物理删除 | ❌ 不可恢复 |

#### 5.2 批量删除（delete_many）

```python
# Repository 代码
async def delete_by_user_id(self, user_id: str):
    result = await self.model.delete_many({"user_id": user_id})
    return result.modified_count
```

**DualStorageModelProxy 不拦截 delete_many**：
- 软删除只标记 `deleted_at`，不从 KV 删除
- 保留完整数据以便恢复

---

## Lite 数据构建

### 构建时机

Lite 数据在以下时机构建：

1. **INSERT 时**: `wrap_insert()` → `LiteModelExtractor.extract_lite_data()`
2. **SAVE 时**: `wrap_save()` → `LiteModelExtractor.extract_lite_data()`

### 提取规则

```python
def extract_lite_data(document) -> Dict[str, Any]:
    """
    从完整 Document 提取 Lite 数据

    提取规则：
    1. ✅ 包含：所有索引字段（Indexed 标记）
    2. ✅ 包含：Settings.query_fields（手动指定）
    3. ✅ 包含：核心字段（id, created_at, updated_at）
    4. ❌ 排除：非索引字段
    5. ❌ 排除：ExpressionField（_id, revision_id）
    """
    indexed_fields = LiteModelExtractor.extract_indexed_fields(type(document))

    # 获取完整数据
    full_data = document.model_dump(
        mode="python",
        exclude={'_id', 'id', 'revision_id'}
    )

    # 过滤：仅保留索引字段
    lite_data = {
        field: value
        for field, value in full_data.items()
        if field in indexed_fields
    }

    return lite_data
```

### MemCell 的 Lite 数据示例

**MemCell Document 定义**:
```python
class MemCell(DocumentBaseWithSoftDelete, AuditBase):
    # 索引字段
    user_id: Optional[Indexed(str)]      # ✅ 包含
    timestamp: Indexed(datetime)         # ✅ 包含
    group_id: Optional[Indexed(str)]     # ✅ 包含

    # 非索引字段
    summary: Optional[str]               # ❌ 不包含
    original_data: Optional[List]        # ❌ 不包含
    tags: Optional[List[str]]            # ❌ 不包含
    keywords: Optional[List[str]]        # ❌ 不包含
    participants: List[str]              # ❌ 不包含
    raw_data: Optional[RawData]          # ❌ 不包含

    class Settings:
        name = "memcells"
        indexes = [
            IndexModel([("user_id", ASCENDING), ("timestamp", DESCENDING)]),
            IndexModel([("group_id", ASCENDING), ("timestamp", DESCENDING)]),
        ]
```

**提取结果**:
```python
lite_data = {
    'user_id': 'user123',
    'timestamp': datetime(2024, 1, 20, 10, 30),
    'group_id': 'group456',
    'created_at': datetime(2024, 1, 20, 10, 30),
    'updated_at': datetime(2024, 1, 20, 10, 30),
    'deleted_at': None,
    'deleted_by': None,
}
```

### 扩展查询字段

如果需要查询非索引字段，可通过 `query_fields` 扩展：

```python
class MemCell(DocumentBaseWithSoftDelete, AuditBase):
    user_id: Indexed(str)
    summary: str  # 非索引字段，但需要查询

    class Settings:
        query_fields = ['summary']  # ← 手动添加到 Lite 数据
```

添加后：
```python
lite_data = {
    'user_id': 'user123',
    'summary': '讨论了新功能',  # ← 现在包含了
    # ...
}
```

---

## 数据流图

### 完整 CRUD 数据流

```
┌─────────────────────────────────────────────────────────────┐
│                    Repository 层                             │
│  • append_memcell(memcell)                                  │
│  • find_by_user_id(user_id)                                 │
│  • update_by_event_id(event_id, data)                       │
│  • delete_by_event_id(event_id)                             │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                  DualStorageMixin 拦截层                     │
│  • self.model = DualStorageModelProxy(MemCell)             │
│  • Monkey Patch: insert(), save(), delete()                │
└─────────────────────────────────────────────────────────────┘
                           ↓
         ┌─────────────────────────────────┐
         │   DualStorageModelProxy         │
         │  • find() → QueryProxy          │
         │  • find_one() → FindOneProxy    │
         │  • update_many()                │
         └─────────────────────────────────┘
                           ↓
    ┌──────────────────────────────────────────┐
    │         LiteModelExtractor               │
    │  • extract_indexed_fields()              │
    │  • extract_lite_data()                   │
    └──────────────────────────────────────────┘
                           ↓
┌──────────────────────┐          ┌─────────────────────────┐
│   MongoDB (Lite)     │          │   KV-Storage (Full)     │
│                      │          │                         │
│  INSERT:             │          │  INSERT:                │
│  ├─ 仅索引字段        │          │  ├─ 完整 JSON 数据       │
│  └─ 200 bytes        │          │  └─ 5KB                 │
│                      │          │                         │
│  FIND:               │          │  FIND:                  │
│  ├─ 高速索引查询      │          │  ├─ 通过 ID 批量加载     │
│  └─ 返回 ID 列表     │          │  └─ 反序列化为对象       │
│                      │          │                         │
│  UPDATE:             │          │  UPDATE:                │
│  ├─ 仅更新索引字段    │          │  ├─ 更新完整数据         │
│  └─ 小事务           │          │  └─ 覆盖写入            │
│                      │          │                         │
│  DELETE (soft):      │          │  DELETE (soft):         │
│  ├─ 标记 deleted_at  │          │  ├─ 更新 deleted_at     │
│  └─ 不删除数据       │          │  └─ 保留完整数据         │
└──────────────────────┘          └─────────────────────────┘
```

---

## FAQ

### Q1: 为什么要双存储？

**A**: 解决 MongoDB 存储成本与查询性能的矛盾

- ❌ **纯 MongoDB**：查询快，但存储大数据成本高（完整数据）
- ❌ **纯 KV**：存储便宜，但查询慢（需扫描所有数据）
- ✅ **双存储**：查询快（MongoDB 索引） + 存储便宜（KV 完整数据）

**成本对比**（以 100 万条 MemCell 为例）:

| 方案 | MongoDB 存储 | KV 存储 | 总成本 | 查询性能 |
|------|-------------|---------|--------|---------|
| 纯 MongoDB | 5GB (完整) | 0 | $$$$ | ⚡⚡⚡ |
| 纯 KV | 0 | 5GB (完整) | $ | 🐢 |
| **双存储** | **200MB (Lite)** | **5GB (Full)** | **$$** | **⚡⚡⚡** |

### Q2: Lite 数据包含哪些字段？

**A**: 仅包含索引字段 + query_fields

**自动包含**:
- `Indexed` 标记的字段（如 `user_id: Indexed(str)`）
- 复合索引中的所有字段
- 核心字段：`id`, `created_at`, `updated_at`, `deleted_at`

**手动添加**:
```python
class Settings:
    query_fields = ['summary', 'tags']  # 需要查询的非索引字段
```

### Q3: 如何判断某个字段是否在 Lite 数据中？

**A**: 查看日志或触发 `LiteStorageQueryError`

```python
# 方式 1: 查看初始化日志
# 日志输出：
# ✅ Lite fields for MemCell: {'id', 'user_id', 'timestamp', 'group_id', ...}

# 方式 2: 尝试查询，系统会报错
await self.model.find({"summary": "会议"}).to_list()
# 抛出 LiteStorageQueryError:
# ❌ Query uses non-indexed fields: {'summary'}
# To fix, add to Settings.query_fields: ['summary']
```

### Q4: KV miss 怎么办？

**A**: KV miss 意味着 MongoDB 有 Lite 数据，但 KV 中没有完整数据

**可能原因**:
1. 旧数据（双存储之前插入的）
2. KV 数据被误删
3. 测试环境数据不同步

**解决方案**:
```python
# 方式 1: 清理旧数据
await repository.hard_delete_by_user_id(user_id)

# 方式 2: 数据迁移（从 MongoDB 重建 KV）
async def migrate_to_dual_storage():
    all_docs = await MemCell.find({}).to_list()
    for doc in all_docs:
        full_data = doc.model_dump(mode="python")
        kv_value = json.dumps(full_data)
        await kv_storage.put(key=str(doc.id), value=kv_value)
```

### Q5: 双存储有性能损耗吗？

**A**: 几乎没有

**INSERT 性能**:
- MongoDB 写入：200 bytes（Lite）
- KV 写入：5KB（Full）
- 总耗时：~10ms（并发写入）

**FIND 性能**:
- MongoDB 查询：~1ms（索引查询）
- KV 批量加载：~5ms（批量获取 100 条）
- 总耗时：~6ms

**对比纯 MongoDB**:
- 纯 MongoDB 查询：~5ms（传输 5KB * 100）
- **双存储更快**（MongoDB 只传输 ID，KV 本地加载）

### Q6: 支持事务吗？

**A**: 支持 MongoDB 事务，KV 不支持事务

```python
async with await repository.start_session() as session:
    async with session.start_transaction():
        await memcell1.insert(session=session)  # MongoDB + KV
        await memcell2.insert(session=session)  # MongoDB + KV
        # MongoDB 事务提交
        # KV 写入独立（无事务）
```

**注意**: KV 写入失败不会回滚 MongoDB

### Q7: 可以禁用双存储吗？

**A**: 可以，移除 `DualStorageMixin` 即可

```python
# 启用双存储
class MemCellRawRepository(
    DualStorageMixin,  # ← 移除这行
    BaseRepository[MemCell],
):
    pass

# 禁用双存储（回退到纯 MongoDB）
class MemCellRawRepository(BaseRepository[MemCell]):
    pass
```

### Q8: 如何监控双存储状态？

**A**: 查看日志

```python
# 插入成功
logger.debug("✅ Inserted to MongoDB: doc_id, lite_size=200B")
logger.debug("✅ Inserted to KV-Storage: doc_id, full_size=5KB")

# KV miss 警告
logger.warning("⚠️  KV miss in find_one for doc_id")

# 查询字段错误
logger.error("❌ Query uses non-indexed fields: {'summary'}")
```

---

## 总结

### 核心优势

1. ✅ **零侵入**: Repository 代码无需改动（仅添加 Mixin）
2. ✅ **透明同步**: MongoDB ↔ KV-Storage 自动同步
3. ✅ **高性能**: MongoDB 索引查询 + KV 批量加载
4. ✅ **低成本**: MongoDB 仅存储 Lite 数据（压缩比 25:1）
5. ✅ **可扩展**: 支持 `query_fields` 灵活扩展

### 适用场景

- ✅ 大数据量存储（百万级以上）
- ✅ 查询频繁（索引字段查询）
- ✅ 数据体积大（单条 >5KB）
- ✅ 成本敏感（MongoDB 存储成本高）

### 不适用场景

- ❌ 小数据量（< 10 万条，纯 MongoDB 更简单）
- ❌ 全文搜索（需要 Elasticsearch）
- ❌ 实时一致性要求高（KV 无事务）

---

**作者**: EverMemOS Team
**最后更新**: 2024-01-21
**版本**: v1.0
