# KV 存储使用指南

## 快速开始

### 1. 配置位置

所有配置在项目根目录的 `.env` 文件中。

### 2. 创建配置文件

```bash
# 复制模板
cp env.template .env

# 编辑配置
vim .env
```

### 3. 配置 KV Storage

在 `.env` 文件中找到 `KV Storage Configuration` 部分，设置 `KV_STORAGE_TYPE`:

- **InMemory (默认)**: `KV_STORAGE_TYPE=inmemory` - 开发/测试用
- **Redis**: `KV_STORAGE_TYPE=redis` - 生产环境，需配置 Redis 连接
- **0G-Storage**: `KV_STORAGE_TYPE=zerog` - 去中心化存储，需配置 `ZEROG_*` 参数

详细配置参数说明请查看 `env.template` 文件中的注释。

### 4. 启动应用

```bash
python src/run.py
```

应用会自动读取 `.env` 配置并初始化对应的 KV Storage。

### 5. 验证配置

查看启动日志：

**InMemory：**
```
✅ In-Memory KV-Storage initialized (data will be lost on restart)
✅ KV-Storage registered to DI container: InMemoryKVStorage
```

**Redis：**
```
✅ Redis KV-Storage initialized successfully
   (Using RedisProvider from DI container)
✅ KV-Storage registered to DI container: RedisKVStorage
```

**0G-Storage：**
```
✅ 0G-Storage KV-Storage initialized successfully
   Stream ID: 000000000000000000000000000000000000000000000000000000000000f2be
   Nodes: http://35.236.80.213:5678... (+1 more)
   Read Node: http://34.31.1.26:6789
   Timeout: 30s, Max Retries: 3
✅ KV-Storage registered to DI container: ZeroGKVStorage
```

---

## 切换 KV Storage

只需修改 `.env` 文件中的 `KV_STORAGE_TYPE` 并重启应用：

```bash
# 切换到 InMemory
KV_STORAGE_TYPE=inmemory

# 切换到 Redis (需配置 REDIS_* 参数)
KV_STORAGE_TYPE=redis

# 切换到 0G-Storage (需配置 ZEROG_* 参数)
KV_STORAGE_TYPE=zerog
```

重启应用：
```bash
python src/run.py
```

**注意：** 切换实现后，旧实现中的数据不会自动迁移。新数据将写入新的存储后端。

---

## 技术细节

### Key 格式

所有 keys 使用 `{collection_name}:{document_id}` 格式：

```
episodic_memories:6979da5797f9041fc0aa063f
event_log_records:507f1f77bcf86cd799439011
foresight_memories:60d5ec49f8d2c07c8a8e4b2a
```

**所有实现统一：**
InMemory、Redis 和 0G-Storage 三种实现使用相同的 key 格式，无额外前缀。

### 数据编码

- **0G-Storage:** 使用 **Base64 编码**（避免不支持 `\n` 和 `,`）
- **Redis:** 直接存储 JSON 字符串
- **InMemory:** 直接存储 JSON 字符串
- 编码/解码由 `encoding_utils.py` 自动处理，对使用者透明

### Delete 操作

- **0G-Storage:** 通过写入空字符串 `""` 实现（墓碑模式）
- **Redis:** 使用 `DEL` 命令直接删除
- **InMemory:** 从字典中删除

### 工作原理

```
应用启动
    ↓
读取 .env 中的 KV_STORAGE_TYPE
    ↓
    ├─ "inmemory" → InMemoryKVStorage()
    ├─ "redis"    → RedisKVStorage() (使用 RedisProvider)
    └─ "zerog"    → ZeroGKVStorage(读取 ZEROG_* 环境变量)
    ↓
register_primary(KVStorageInterface, kv_storage)
    ↓
其他组件通过 get_bean_by_type(KVStorageInterface) 获取实例
```

---

## 三种实现对比

| 特性 | InMemory | Redis | 0G-Storage |
|------|---------|-------|-----------|
| **数据持久化** | ❌ 重启丢失 | ✅ 持久化 | ✅ 持久化 |
| **跨进程共享** | ❌ | ✅ | ✅ |
| **性能** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **配置复杂度** | 简单 | 中等 | 复杂 |
| **适用场景** | 开发/测试 | 生产环境 | 去中心化 |
| **依赖** | 无 | Redis 服务 | 0g-storage-client |

---

## 关键文件

| 文件 | 说明 |
|------|------|
| `.env` | **配置文件（需要创建）** |
| `.env.zerog.example` | 配置模板 |
| `src/core/lifespan/kv_storage_lifespan.py` | 初始化逻辑 |
| `src/infra_layer/adapters/out/persistence/kv_storage/in_memory_kv_storage.py` | InMemory 实现 |
| `src/infra_layer/adapters/out/persistence/kv_storage/redis_kv_storage.py` | Redis 实现 |
| `src/infra_layer/adapters/out/persistence/kv_storage/zerog_kv_storage.py` | 0G-Storage 实现 |
| `src/infra_layer/adapters/out/persistence/kv_storage/encoding_utils.py` | Base64 编解码工具 |

---

## 常见问题

### Q: 如何查看当前使用的是哪个 KV Storage？

**A:** 查看应用启动日志，或调用调试接口：
```bash
curl http://localhost:8000/api/v1/debug/kv-storage/check-latest
```

返回的 `kv_storage_type` 字段显示当前实现：
- `InMemoryKVStorage` - 内存存储
- `RedisKVStorage` - Redis 存储
- `ZeroGKVStorage` - 0G-Storage

### Q: 切换 KV Storage 后数据会丢失吗？

**A:**
- InMemory → Redis/0G-Storage：InMemory 数据会丢失（需要迁移脚本）
- Redis → InMemory：Redis 数据保留（但不会加载到内存）
- Redis → 0G-Storage：Redis 数据保留（需要迁移脚本）
- 0G-Storage → Redis：0G-Storage 数据保留（需要迁移脚本）
- 切换后新数据写入新的存储后端

### Q: 不同 KV Storage 实现的 key 格式一致吗？

**A:** 是的，所有三种实现（InMemory、Redis、0G-Storage）使用相同的 key 格式：
```
{collection_name}:{document_id}
例如: episodic_memories:6979da5797f9041fc0aa063f
```

这确保了在不同实现之间切换时，key 格式保持一致，避免数据丢失。

### Q: 0g-storage-client 命令找不到怎么办？

**A:** 需要先安装 0g-storage-client CLI 工具，参考 0G 官方文档。

### Q: ZEROG_WALLET_KEY 如何安全存储？

**A:**
- 开发环境：存放在 `.env` 文件中（确保在 `.gitignore` 中）
- 生产环境：使用密钥管理服务（AWS Secrets Manager、HashiCorp Vault 等）
- 永远不要提交私钥到 Git

### Q: 为什么不需要手动给参数加双引号？

**A:** Python `subprocess` 使用列表模式时，每个列表元素自动作为独立参数传递给程序，无需手动加引号。特殊字符（冒号、逗号）会被正确处理。

### Q: 生产环境应该选择 Redis 还是 0G-Storage？

**A:** 取决于需求：
- **选择 Redis：**
  - 需要高性能读写
  - 需要跨进程/服务器共享数据
  - 已有 Redis 基础设施
  - 标准的生产环境方案

- **选择 0G-Storage：**
  - 需要去中心化存储
  - 公司基础设施支持 0G
  - 对数据主权有特殊要求

---

## 安全提示

1. **永远不要提交 `.env` 文件到 Git**
   - 确保 `.env` 在 `.gitignore` 中
   - 只提交 `.env.example` 模板

2. **保护私钥和密码**
   - 不要在代码中硬编码
   - 限制 `.env` 文件权限：`chmod 600 .env`
   - 生产环境使用密钥管理服务

3. **环境隔离**
   - 开发环境使用 InMemory
   - 测试环境使用独立的 Redis/0G 实例
   - 生产环境使用专用配置

---

## 故障排查

### 启动失败：Missing required 0G-Storage configuration

**原因：** 缺少必需的环境变量

**解决：** 检查 `.env` 文件是否包含：
- `ZEROG_NODES`
- `ZEROG_STREAM_ID`
- `ZEROG_RPC_URL`
- `ZEROG_READ_NODE`
- `ZEROG_WALLET_KEY`

### 应用使用 InMemoryKVStorage 但配置了 redis/zerog

**可能原因：**
1. `.env` 文件不在项目根目录
2. `KV_STORAGE_TYPE` 拼写错误
3. 环境变量未正确加载

**解决：** 检查启动日志，确认环境变量加载情况。

### Redis 连接失败

**可能原因：**
1. Redis 服务未启动
2. `REDIS_HOST` 或 `REDIS_PORT` 配置错误
3. 网络连接问题

**解决：**
- 检查 Redis 服务状态：`redis-cli ping`
- 确认配置正确

---

**实施日期：** 2026-01-29
**当前状态：** ✅ 可用
**支持的实现：** InMemory, Redis, 0G-Storage
**所有实现均已完成并可用！**
