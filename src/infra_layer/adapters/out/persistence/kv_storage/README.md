# MemCell KV-Storage Implementation

## Overview

This module implements a dual-write strategy for MemCell documents, storing data in both MongoDB (primary) and a key-value storage (secondary) for validation and backup purposes.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   MemCellRawRepository                       │
│                                                              │
│  ┌───────────────┐              ┌──────────────────┐       │
│  │   Write Ops   │              │    Read Ops      │       │
│  │ ─────────────│              │ ──────────────│       │
│  │ · append      │              │ · get_by_id      │       │
│  │ · update      │              │ · get_by_ids     │       │
│  │ · delete      │              │                  │       │
│  └───────┬───────┘              └────────┬─────────┘       │
│          │                               │                  │
└──────────┼───────────────────────────────┼──────────────────┘
           │                               │
           ▼                               ▼
    ┌──────────────┐              ┌──────────────┐
    │   MongoDB    │              │   MongoDB    │
    │  (Primary)   │              │  (Primary)   │
    └──────────────┘              └──────┬───────┘
           │                              │
           │ Dual Write                   │ Validation
           ▼                              ▼
    ┌──────────────┐              ┌──────────────┐
    │  KV-Storage  │              │  KV-Storage  │
    │ (Secondary)  │              │ (Secondary)  │
    └──────────────┘              └──────────────┘
```

## Components

### 1. MemCellKVStorage (Interface)
- Abstract interface defining KV-Storage contract
- Methods: `put()`, `get()`, `delete()`, `batch_get()`, `batch_delete()`, `close()`
- Designed for implementation swapping via configuration

### 2. InMemoryKVStorage (Implementation)
- Dict-based in-memory implementation
- Thread-safe with Lock
- Suitable for:
  - Development and debugging
  - Testing
  - Small-scale deployments
- NOT suitable for:
  - Production (data lost on restart)
  - Multi-process deployments
  - Large datasets

### 3. Validator Utilities
- `compare_memcell_data()`: Compares MongoDB and KV-Storage data
- `log_inconsistency()`: Logs data inconsistencies for monitoring
- `validate_json_serialization()`: Validates JSON format

## Usage

### Automatic Registration

The `InMemoryKVStorage` is automatically registered with the DI container via the `@repository` decorator:

```python
@repository("memcell_kv_storage", primary=True)
class InMemoryKVStorage(MemCellKVStorage):
    ...
```

### Write Operations

All write operations automatically dual-write to both MongoDB and KV-Storage:

```python
# INSERT
memcell_repo = get_bean_by_type(MemCellRawRepository)
result = await memcell_repo.append_memcell(memcell)
# ✅ Writes to MongoDB
# ✅ Writes to KV-Storage (non-blocking, failures logged)

# UPDATE
result = await memcell_repo.update_by_event_id(event_id, update_data)
# ✅ Updates MongoDB
# ✅ Updates KV-Storage

# DELETE (single)
success = await memcell_repo.delete_by_event_id(event_id)
# ✅ Deletes from MongoDB
# ✅ Deletes from KV-Storage

# DELETE (batch)
count = await memcell_repo.delete_by_user_id(user_id)
# ✅ Deletes from MongoDB
# ✅ Batch deletes from KV-Storage
```

### Read Operations with Validation

Read operations can optionally validate against KV-Storage:

```python
# Single read with validation (default: enabled)
memcell = await memcell_repo.get_by_event_id(event_id)
# ✅ Reads from MongoDB (authoritative)
# ✅ Validates against KV-Storage
# ⚠️  Logs inconsistencies if found
# ✅ Returns MongoDB data (always)

# Single read without validation
memcell = await memcell_repo.get_by_event_id(event_id, enable_kv_validation=False)
# ✅ Reads from MongoDB only

# Batch read with validation (default: disabled for performance)
memcells = await memcell_repo.get_by_event_ids(event_ids, enable_kv_validation=True)
# ✅ Reads from MongoDB
# ✅ Batch validates against KV-Storage if enabled
# ✅ Returns MongoDB data
```

## Error Handling Strategy

| Scenario | Strategy | Impact |
|----------|----------|--------|
| **KV-Storage write failure** | Log warning, continue | MongoDB write succeeds ✅ |
| **KV-Storage read failure** | Log warning, return MongoDB data | Read succeeds ✅ |
| **Data inconsistency detected** | Log error with details, return MongoDB data | Read succeeds ✅ |
| **MongoDB write/read failure** | Raise exception | Operation fails ❌ |

**Key Principle**: MongoDB is authoritative. KV-Storage issues never block operations.

## Serialization Consistency

### Important Considerations

1. **JSON Field Order**: Use `by_alias=True, exclude_none=False` for consistent serialization
2. **Date/Time Format**: Pydantic/Beanie use ISO 8601 format
3. **ObjectId Handling**: Automatically converted to strings
4. **None vs Missing Fields**: Include None values with `exclude_none=False`

### Recommended Configuration

```python
# Consistent serialization
json_value = memcell.model_dump_json(
    by_alias=True,      # Use field aliases
    exclude_none=False, # Include None values
)
```

## Switching Between Implementations

### Current Setup (In-Memory)

The in-memory implementation is active by default due to the `@repository` decorator with `primary=True`.

### Adding a Custom Implementation

To add a custom KV-Storage implementation (e.g., RocksDB):

1. **Create Implementation**:
```python
# src/infra_layer/adapters/out/persistence/kv_storage/rocksdb_kv_storage.py

from .memcell_kv_storage import MemCellKVStorage
from core.di.decorators import repository

@repository("memcell_kv_storage", primary=False)  # Set primary=False
class RocksDBKVStorage(MemCellKVStorage):
    async def put(self, key: str, value: str) -> bool:
        # RocksDB implementation
        ...
```

2. **Switch Primary**:
```python
# Change primary flag:
# in_memory_kv_storage.py: primary=False
# rocksdb_kv_storage.py: primary=True
```

3. **Configuration-Based Switching** (Recommended):
```python
# In your settings/config:
KV_STORAGE_TYPE = "rocksdb"  # or "inmemory"

# In __init__.py or a factory:
if KV_STORAGE_TYPE == "inmemory":
    @repository("memcell_kv_storage", primary=True)
    class ActiveKVStorage(InMemoryKVStorage):
        pass
else:
    @repository("memcell_kv_storage", primary=True)
    class ActiveKVStorage(RocksDBKVStorage):
        pass
```

## Monitoring and Debugging

### Log Levels

- **DEBUG**: KV-Storage operations (put/get/delete success)
- **WARNING**: KV-Storage failures, missing data
- **ERROR**: Data inconsistencies detected
- **INFO**: KV-Storage initialization, batch operations

### Key Metrics to Monitor

1. `kv_write_failure_count`: Number of failed KV writes
2. `kv_read_failure_count`: Number of failed KV reads
3. `data_inconsistency_count`: Number of detected inconsistencies
4. `kv_write_latency`: Average KV write latency
5. `kv_read_latency`: Average KV read latency

### Debug In-Memory Storage Stats

```python
kv_storage = get_bean_by_type(MemCellKVStorage)
if isinstance(kv_storage, InMemoryKVStorage):
    stats = kv_storage.get_stats()
    print(f"Entries: {stats['entry_count']}")
    print(f"Total size: {stats['total_size_bytes']} bytes")
```

## Transaction Considerations

### Current Behavior

KV-Storage writes occur immediately after MongoDB writes, even within transactions. This means:

```python
async with session.start_transaction():
    await memcell_repo.append_memcell(memcell, session=session)
    # MongoDB write is transactional ✅
    # KV-Storage write is immediate ⚠️
    # If transaction rolls back, KV may have stale data
```

### Future Enhancement

For strict consistency, KV-Storage writes should occur after transaction commit:

```python
# Pseudo-code for future implementation
async with session.start_transaction():
    await memcell_repo.append_memcell(memcell, session=session)
    session.register_post_commit_callback(
        lambda: kv_storage.put(key, value)
    )
    await session.commit_transaction()
    # KV-Storage write happens here ✅
```

## Testing

### Unit Tests

```bash
# Test KV-Storage interface
pytest tests/test_kv_storage.py

# Test validator utilities
pytest tests/test_validator.py

# Test repository with KV-Storage
pytest tests/test_memcell_raw_repository.py
```

### Integration Tests

```bash
# Test dual-write consistency
pytest tests/integration/test_memcell_dual_write.py
```

## Performance Considerations

### Write Operations
- **Overhead**: Minimal (~5-10ms for in-memory KV)
- **Impact**: Asynchronous, non-blocking
- **Optimization**: Consider batching for bulk operations

### Read Operations
- **Validation Overhead**: ~5-20ms per item (in-memory)
- **Recommendation**: Disable validation for large batch queries
- **Default Behavior**:
  - Single reads: Validation ON
  - Batch reads: Validation OFF

### Memory Usage (In-Memory Implementation)
- **Per Entry**: ~1-5KB (depending on MemCell size)
- **For 100K entries**: ~100-500MB
- **Monitoring**: Use `get_stats()` to track usage

## Future Enhancements

1. **Persistent Implementations**:
   - RocksDB integration
   - LevelDB integration
   - Redis integration

2. **Transaction Support**:
   - Post-commit KV writes
   - Rollback handling

3. **Data Migration Tools**:
   - Sync existing MongoDB data to KV
   - Repair inconsistencies

4. **Configuration System**:
   - Environment-based switching
   - Feature flags for KV operations

5. **Monitoring Integration**:
   - Prometheus metrics
   - Alerting on inconsistencies

## Troubleshooting

### KV-Storage Not Initialized

**Symptom**: Logs show "KV-Storage not available"

**Solution**:
1. Verify `@repository` decorator is present
2. Check DI scanner is scanning the kv_storage package
3. Verify no import errors in kv_storage modules

### Data Inconsistencies

**Symptom**: Error logs showing data mismatches

**Causes**:
1. Serialization format changed
2. MongoDB updated but KV write failed
3. Transaction rollback (KV write succeeded)

**Solutions**:
1. Review serialization settings
2. Check KV-Storage write failure logs
3. Implement post-commit KV writes

### Performance Issues

**Symptom**: Slow read operations

**Solutions**:
1. Disable validation for batch queries: `enable_kv_validation=False`
2. Use pagination for large result sets
3. Consider persistent KV-Storage with better performance

## License

Internal use only. Part of EverMemOS project.
