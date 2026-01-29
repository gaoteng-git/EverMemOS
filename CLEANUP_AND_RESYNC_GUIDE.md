# Cleanup and Resync Guide

This guide provides complete steps to clean up existing data in Milvus and Elasticsearch, then resync all memory data from MongoDB.

---

## ⚠️ WARNING

**These operations will DELETE ALL DATA in Milvus and Elasticsearch!**

- Make sure you have backups if needed
- This is recommended for development/test environments
- For production, consider incremental sync instead

---

## 📋 Table of Contents

1. [Quick Start: Full Cleanup and Resync](#quick-start-full-cleanup-and-resync)
2. [Step-by-Step Manual Process](#step-by-step-manual-process)
3. [Selective Cleanup](#selective-cleanup)
4. [Verification](#verification)
5. [Troubleshooting](#troubleshooting)

---

## 🚀 Quick Start: Full Cleanup and Resync

Use this one-command approach to clean everything and resync all data:

```bash
uv run python src/bootstrap.py src/devops_scripts/data_fix/full_resync.py
```

This script will:
1. ✅ Clean up all Milvus collections (episodic_memory, event_log, foresight)
2. ✅ Clean up all Elasticsearch indices (episodic-memory, event-log, foresight)
3. ✅ Sync all Episodic Memory data from MongoDB → Milvus
4. ✅ Sync all Episodic Memory data from MongoDB → Elasticsearch
5. ✅ Sync all Event Log data from MongoDB → Milvus
6. ✅ Sync all Event Log data from MongoDB → Elasticsearch
7. ✅ Sync all Foresight data from MongoDB → Milvus
8. ✅ Sync all Foresight data from MongoDB → Elasticsearch

**Time estimate:** 5-30 minutes depending on data volume

---

## 📝 Step-by-Step Manual Process

### Step 1: Clean Up Milvus Collections

#### Option A: Clean all collections

```bash
uv run python src/bootstrap.py src/devops_scripts/data_fix/cleanup_milvus.py --all
```

**Confirmation prompt:**
```
⚠️  WARNING: This will DELETE ALL DATA in the following collections:
  - episodic_memory
  - event_log
  - foresight

Are you sure you want to proceed? (yes/no):
```

Type `yes` and press Enter.

#### Option B: Clean specific collection

```bash
# Clean only episodic_memory
uv run python src/bootstrap.py src/devops_scripts/data_fix/cleanup_milvus.py --collection episodic_memory

# Clean only event_log
uv run python src/bootstrap.py src/devops_scripts/data_fix/cleanup_milvus.py --collection event_log

# Clean only foresight
uv run python src/bootstrap.py src/devops_scripts/data_fix/cleanup_milvus.py --collection foresight
```

---

### Step 2: Clean Up Elasticsearch Indices

#### Option A: Clean all indices

```bash
uv run python src/bootstrap.py src/devops_scripts/data_fix/cleanup_es.py --all
```

**Confirmation prompt:**
```
⚠️  WARNING: This will DELETE ALL DATA in the following indices:
  - episodic-memory
  - event-log
  - foresight

Are you sure you want to proceed? (yes/no):
```

Type `yes` and press Enter.

#### Option B: Clean specific index

```bash
# Clean only episodic-memory
uv run python src/bootstrap.py src/devops_scripts/data_fix/cleanup_es.py --index episodic-memory

# Clean only event-log
uv run python src/bootstrap.py src/devops_scripts/data_fix/cleanup_es.py --index event-log

# Clean only foresight
uv run python src/bootstrap.py src/devops_scripts/data_fix/cleanup_es.py --index foresight
```

---

### Step 3: Sync Data from MongoDB to Milvus

#### Sync Episodic Memory

```bash
# Sync all documents
uv run python src/bootstrap.py src/devops_scripts/data_fix/milvus_sync_docs.py \
  --collection-name episodic_memory

# Sync with custom batch size
uv run python src/bootstrap.py src/devops_scripts/data_fix/milvus_sync_docs.py \
  --collection-name episodic_memory \
  --batch-size 1000

# Sync only recent data (last 30 days)
uv run python src/bootstrap.py src/devops_scripts/data_fix/milvus_sync_docs.py \
  --collection-name episodic_memory \
  --days 30

# Sync with limit (test with small dataset first)
uv run python src/bootstrap.py src/devops_scripts/data_fix/milvus_sync_docs.py \
  --collection-name episodic_memory \
  --limit 1000
```

#### Sync Event Log

```bash
# Sync all documents
uv run python src/bootstrap.py src/devops_scripts/data_fix/milvus_sync_docs.py \
  --collection-name event_log

# Sync last 7 days with batch size 1000
uv run python src/bootstrap.py src/devops_scripts/data_fix/milvus_sync_docs.py \
  --collection-name event_log \
  --batch-size 1000 \
  --days 7
```

#### Sync Foresight

```bash
# Sync all documents
uv run python src/bootstrap.py src/devops_scripts/data_fix/milvus_sync_docs.py \
  --collection-name foresight

# Sync last 30 days
uv run python src/bootstrap.py src/devops_scripts/data_fix/milvus_sync_docs.py \
  --collection-name foresight \
  --days 30
```

---

### Step 4: Sync Data from MongoDB to Elasticsearch

#### Sync Episodic Memory

```bash
# Sync all documents
uv run python src/bootstrap.py src/devops_scripts/data_fix/es_sync_docs.py \
  --index-name episodic-memory

# Sync with custom batch size
uv run python src/bootstrap.py src/devops_scripts/data_fix/es_sync_docs.py \
  --index-name episodic-memory \
  --batch-size 1000

# Sync only recent data (last 30 days)
uv run python src/bootstrap.py src/devops_scripts/data_fix/es_sync_docs.py \
  --index-name episodic-memory \
  --days 30

# Sync with limit (test with small dataset first)
uv run python src/bootstrap.py src/devops_scripts/data_fix/es_sync_docs.py \
  --index-name episodic-memory \
  --limit 1000
```

#### Sync Event Log

```bash
# Sync all documents
uv run python src/bootstrap.py src/devops_scripts/data_fix/es_sync_docs.py \
  --index-name event-log

# Sync last 7 days with batch size 1000
uv run python src/bootstrap.py src/devops_scripts/data_fix/es_sync_docs.py \
  --index-name event-log \
  --batch-size 1000 \
  --days 7
```

#### Sync Foresight

```bash
# Sync all documents
uv run python src/bootstrap.py src/devops_scripts/data_fix/es_sync_docs.py \
  --index-name foresight

# Sync last 30 days
uv run python src/bootstrap.py src/devops_scripts/data_fix/es_sync_docs.py \
  --index-name foresight \
  --days 30
```

---

## 🎯 Selective Cleanup

### Scenario 1: Only clean Milvus, keep ES data

```bash
# Step 1: Clean Milvus
uv run python src/bootstrap.py src/devops_scripts/data_fix/cleanup_milvus.py --all

# Step 2: Resync to Milvus only
uv run python src/bootstrap.py src/devops_scripts/data_fix/milvus_sync_docs.py --collection-name episodic_memory
uv run python src/bootstrap.py src/devops_scripts/data_fix/milvus_sync_docs.py --collection-name event_log
uv run python src/bootstrap.py src/devops_scripts/data_fix/milvus_sync_docs.py --collection-name foresight
```

### Scenario 2: Only clean ES, keep Milvus data

```bash
# Step 1: Clean ES
uv run python src/bootstrap.py src/devops_scripts/data_fix/cleanup_es.py --all

# Step 2: Resync to ES only
uv run python src/bootstrap.py src/devops_scripts/data_fix/es_sync_docs.py --index-name episodic-memory
uv run python src/bootstrap.py src/devops_scripts/data_fix/es_sync_docs.py --index-name event-log
uv run python src/bootstrap.py src/devops_scripts/data_fix/es_sync_docs.py --index-name foresight
```

### Scenario 3: Clean and resync only one memory type

```bash
# Example: Episodic Memory only

# Step 1: Clean
uv run python src/bootstrap.py src/devops_scripts/data_fix/cleanup_milvus.py --collection episodic_memory
uv run python src/bootstrap.py src/devops_scripts/data_fix/cleanup_es.py --index episodic-memory

# Step 2: Resync
uv run python src/bootstrap.py src/devops_scripts/data_fix/milvus_sync_docs.py --collection-name episodic_memory
uv run python src/bootstrap.py src/devops_scripts/data_fix/es_sync_docs.py --index-name episodic-memory
```

---

## ✅ Verification

### Verify Milvus Collection Count

Check document counts directly in Milvus:

```bash
# Use Milvus CLI or Python script
from pymilvus import connections, Collection

connections.connect(host="localhost", port="19530")

# Check episodic_memory
col = Collection("episodic_memory_memsys")
print(f"Episodic Memory count: {col.num_entities}")

# Check event_log
col = Collection("event_log_memsys")
print(f"Event Log count: {col.num_entities}")

# Check foresight
col = Collection("foresight_memsys")
print(f"Foresight count: {col.num_entities}")
```

### Verify Elasticsearch Index Count

```bash
# Check episodic-memory
curl -X GET "http://localhost:19200/episodic-memory-memsys/_count?pretty"

# Check event-log
curl -X GET "http://localhost:19200/event-log-memsys/_count?pretty"

# Check foresight
curl -X GET "http://localhost:19200/foresight-memsys/_count?pretty"
```

### Compare with MongoDB Count

```bash
# MongoDB document counts
mongosh mongodb://localhost:27017/memsys --eval "
  db.episodic_memories.countDocuments({});
  db.event_log_records.countDocuments({});
  db.foresight_records.countDocuments({});
"
```

---

## 🔧 Troubleshooting

### Issue 1: "Collection does not exist" in Milvus

**Cause:** Collection hasn't been created yet.

**Solution:** The cleanup script will recreate it automatically. If you get errors during sync, make sure the application has been started at least once to initialize collections.

### Issue 2: "Index does not exist" in Elasticsearch

**Cause:** Index hasn't been created yet.

**Solution:** Indices are created automatically when the application starts. Restart the application if needed.

### Issue 3: Sync script shows "0 documents processed"

**Possible causes:**
- MongoDB is empty
- Filter conditions (--days, --limit) exclude all documents
- MongoDB connection issues

**Solution:**
```bash
# Check MongoDB has data
mongosh mongodb://localhost:27017/memsys --eval "db.episodic_memories.countDocuments({})"

# Try syncing without filters
uv run python src/bootstrap.py src/devops_scripts/data_fix/milvus_sync_docs.py --collection-name episodic_memory
```

### Issue 4: "Missing vector field" warnings

**Cause:** Some documents don't have embeddings yet.

**Solution:** These documents will be skipped. Make sure embeddings are generated before syncing, or regenerate embeddings for those documents.

### Issue 5: Out of memory errors

**Cause:** Batch size too large.

**Solution:** Reduce batch size:
```bash
# Use smaller batch size
uv run python src/bootstrap.py src/devops_scripts/data_fix/milvus_sync_docs.py \
  --collection-name episodic_memory \
  --batch-size 100
```

---

## 📊 Summary of Commands

### Full Cleanup and Resync (One Command)

```bash
uv run python src/bootstrap.py src/devops_scripts/data_fix/full_resync.py
```

### Manual Step-by-Step

```bash
# 1. Cleanup
uv run python src/bootstrap.py src/devops_scripts/data_fix/cleanup_milvus.py --all
uv run python src/bootstrap.py src/devops_scripts/data_fix/cleanup_es.py --all

# 2. Sync to Milvus
uv run python src/bootstrap.py src/devops_scripts/data_fix/milvus_sync_docs.py --collection-name episodic_memory
uv run python src/bootstrap.py src/devops_scripts/data_fix/milvus_sync_docs.py --collection-name event_log
uv run python src/bootstrap.py src/devops_scripts/data_fix/milvus_sync_docs.py --collection-name foresight

# 3. Sync to ES
uv run python src/bootstrap.py src/devops_scripts/data_fix/es_sync_docs.py --index-name episodic-memory
uv run python src/bootstrap.py src/devops_scripts/data_fix/es_sync_docs.py --index-name event-log
uv run python src/bootstrap.py src/devops_scripts/data_fix/es_sync_docs.py --index-name foresight
```

---

## 🎉 Done!

After completing these steps, your Milvus and Elasticsearch should have fresh data synced from MongoDB.

For questions or issues, check the logs in the output or refer to the troubleshooting section above.
