# List Storage Systems Guide

Quick reference for listing collections and indices in Milvus and Elasticsearch.

---

## 🚀 Quick Commands

### List Everything (Recommended)

```bash
# List both Milvus and Elasticsearch with comparison
uv run python src/bootstrap.py src/devops_scripts/data_fix/list_all_storage.py
```

**Output example:**
```
================================================================================
📊 STORAGE SYSTEMS OVERVIEW
================================================================================

================================================================================
🗄️  MILVUS COLLECTIONS
================================================================================
Found 3 collection(s):

Collection Name                          Entities        Loaded
-----------------------------------------------------------------
episodic_memory_memsys_20260124          15,234          Yes
event_log_memsys_20260124                8,567           Yes
foresight_memsys_20260124                2,341           Yes

================================================================================
🔍 ELASTICSEARCH INDICES
================================================================================
Found 3 index/indices:

Index Name                                         Docs Count      Store Size      Health
------------------------------------------------------------------------------------------
episodic-memory-memsys-20260124                    15,234          45.2mb          green
event-log-memsys-20260124                          8,567           12.3mb          green
foresight-memsys-20260124                          2,341           5.8mb           green

================================================================================
📈 SUMMARY COMPARISON
================================================================================

Memory Type          Milvus               Elasticsearch
------------------------------------------------------------
Episodic Memory      15,234               15,234
Event Log            8,567                8,567
Foresight            2,341                2,341
```

---

## 📋 List Milvus Collections

### Method 1: Python Script (Recommended)

```bash
uv run python src/bootstrap.py src/devops_scripts/data_fix/list_milvus_collections.py
```

**Output:**
```
================================================================================
📊 Milvus Collections
================================================================================
Found 3 collection(s):

Collection Name                          Entities        Loaded
-----------------------------------------------------------------
episodic_memory_memsys_20260124          15,234          Yes
event_log_memsys_20260124                8,567           Yes
foresight_memsys_20260124                2,341           Yes
```

### Method 2: Using Python Directly

```python
from pymilvus import connections, utility, Collection

# Connect
connections.connect(host="localhost", port="19530")

# List all collections
collections = utility.list_collections()
print(f"Collections: {collections}")

# Get details for each collection
for name in collections:
    col = Collection(name)
    col.flush()
    print(f"{name}: {col.num_entities} entities")

# Disconnect
connections.disconnect("default")
```

### Method 3: Using Milvus CLI (if installed)

```bash
# Install Milvus CLI first
pip install milvus-cli

# Start CLI
milvus_cli

# Inside CLI
> connect -h localhost -p 19530
> list collections
> describe collection -c episodic_memory_memsys
```

### Method 4: Using HTTP API

```bash
# List collections
curl -X GET "http://localhost:19530/api/v1/collections" | jq

# Get collection stats
curl -X GET "http://localhost:19530/api/v1/collection/episodic_memory_memsys/stats" | jq
```

---

## 🔍 List Elasticsearch Indices

### Method 1: Python Script (Recommended)

```bash
uv run python src/bootstrap.py src/devops_scripts/data_fix/list_es_indices.py
```

**Output:**
```
================================================================================
📊 Elasticsearch Indices
================================================================================
Found 3 index/indices:

Index Name                                         Docs Count      Store Size      Health
------------------------------------------------------------------------------------------
episodic-memory-memsys-20260124                    15,234          45.2mb          green
event-log-memsys-20260124                          8,567           12.3mb          green
foresight-memsys-20260124                          2,341           5.8mb           green

📈 Summary by Memory Type:
  episodic-memory: 15,234 documents
  event-log: 8,567 documents
  foresight: 2,341 documents
```

### Method 2: Using curl (Simple)

```bash
# List all indices (simple format)
curl -X GET "http://localhost:19200/_cat/indices?v"

# List all indices (JSON format)
curl -X GET "http://localhost:19200/_cat/indices?format=json&pretty"

# List only memory-related indices
curl -X GET "http://localhost:19200/_cat/indices?format=json&pretty" | \
  jq '.[] | select(.index | contains("memory") or contains("log") or contains("foresight"))'
```

**Output:**
```
health status index                                    uuid                   pri rep docs.count docs.deleted store.size pri.store.size
green  open   episodic-memory-memsys-20260124          xB2fK9kZQm-iJH8N9vRZWQ   1   0      15234            0     45.2mb         45.2mb
green  open   event-log-memsys-20260124                yC3gL0lARn-jKI9O0wSaXR   1   0       8567            0     12.3mb         12.3mb
green  open   foresight-memsys-20260124                zD4hM1mBSo-kLJ0P1xTbYS   1   0       2341            0      5.8mb          5.8mb
```

### Method 3: Using curl (Detailed)

```bash
# Get specific index details
curl -X GET "http://localhost:19200/episodic-memory-memsys/_stats?pretty"

# Get document count only
curl -X GET "http://localhost:19200/episodic-memory-memsys/_count?pretty"

# Get mapping (schema)
curl -X GET "http://localhost:19200/episodic-memory-memsys/_mapping?pretty"

# Get settings
curl -X GET "http://localhost:19200/episodic-memory-memsys/_settings?pretty"
```

### Method 4: Using Python Directly

```python
from elasticsearch import Elasticsearch

# Connect
es = Elasticsearch(["http://localhost:19200"])

# List all indices
indices = es.cat.indices(format="json")
for idx in indices:
    if not idx['index'].startswith('.'):  # Skip system indices
        print(f"{idx['index']}: {idx['docs.count']} docs")

# Get specific index count
count = es.count(index="episodic-memory-memsys")
print(f"Count: {count['count']}")
```

---

## 🔧 Advanced Queries

### Count Documents by Memory Type (Milvus)

```python
from pymilvus import connections, Collection

connections.connect(host="localhost", port="19530")

collections = {
    'episodic_memory': 'episodic_memory_memsys',
    'event_log': 'event_log_memsys',
    'foresight': 'foresight_memsys'
}

for name, collection_name in collections.items():
    try:
        col = Collection(collection_name)
        col.flush()
        print(f"{name}: {col.num_entities:,} documents")
    except Exception as e:
        print(f"{name}: Not found or error")
```

### Count Documents by Memory Type (Elasticsearch)

```bash
# Episodic Memory
curl -X GET "http://localhost:19200/episodic-memory-memsys/_count?pretty"

# Event Log
curl -X GET "http://localhost:19200/event-log-memsys/_count?pretty"

# Foresight
curl -X GET "http://localhost:19200/foresight-memsys/_count?pretty"
```

### Search for Specific Patterns

```bash
# Find all indices matching a pattern
curl -X GET "http://localhost:19200/_cat/indices/episodic-memory*?v"

# Find all indices with "memsys" in the name
curl -X GET "http://localhost:19200/_cat/indices/*memsys*?v"
```

---

## 📊 Compare MongoDB, Milvus, and ES Counts

### Quick Comparison Script

```bash
# MongoDB counts
mongosh mongodb://localhost:27017/memsys --quiet --eval "
  print('MongoDB:');
  print('  Episodic Memory:', db.episodic_memories.countDocuments({}));
  print('  Event Log:', db.event_log_records.countDocuments({}));
  print('  Foresight:', db.foresight_records.countDocuments({}));
"

# Milvus counts
uv run python src/bootstrap.py src/devops_scripts/data_fix/list_milvus_collections.py

# ES counts
uv run python src/bootstrap.py src/devops_scripts/data_fix/list_es_indices.py
```

### One-line Comparison

```bash
# MongoDB
echo "MongoDB:" && mongosh mongodb://localhost:27017/memsys --quiet --eval "printjson({episodic: db.episodic_memories.countDocuments({}), event_log: db.event_log_records.countDocuments({}), foresight: db.foresight_records.countDocuments({})})"

# Milvus (requires Python)
python3 -c "from pymilvus import connections, Collection; connections.connect('localhost', '19530'); print('Milvus:', {n: Collection(n+'_memsys').num_entities for n in ['episodic_memory', 'event_log', 'foresight']})"

# ES
curl -s http://localhost:19200/_cat/indices?format=json | jq '[.[] | select(.index | contains("memory") or contains("log") or contains("foresight")) | {index: .index, count: ."docs.count"}]'
```

---

## 🛠️ Troubleshooting

### Issue: "Connection refused" for Milvus

**Check if Milvus is running:**
```bash
docker ps | grep milvus
# or
systemctl status milvus
```

**Check Milvus port:**
```bash
netstat -tulpn | grep 19530
```

### Issue: "Connection refused" for Elasticsearch

**Check if ES is running:**
```bash
docker ps | grep elasticsearch
# or
systemctl status elasticsearch
```

**Check ES port:**
```bash
netstat -tulpn | grep 19200
```

**Test connection:**
```bash
curl http://localhost:19200
```

### Issue: Collections/Indices not found

**Possible causes:**
1. Application hasn't been started yet (collections/indices not initialized)
2. Different namespace/tenant configuration
3. Collections/indices were deleted

**Solution:**
Start the application at least once to initialize:
```bash
uv run python src/bootstrap.py
```

---

## 📋 Summary of Commands

| Task | Command |
|------|---------|
| **List everything** | `uv run python src/bootstrap.py src/devops_scripts/data_fix/list_all_storage.py` |
| **List Milvus only** | `uv run python src/bootstrap.py src/devops_scripts/data_fix/list_milvus_collections.py` |
| **List ES only** | `uv run python src/bootstrap.py src/devops_scripts/data_fix/list_es_indices.py` |
| **ES indices (curl)** | `curl -X GET "http://localhost:19200/_cat/indices?v"` |
| **ES count** | `curl -X GET "http://localhost:19200/episodic-memory-memsys/_count?pretty"` |
| **MongoDB count** | `mongosh mongodb://localhost:27017/memsys --eval "db.episodic_memories.countDocuments({})"` |

---

## 🎯 Quick Health Check

Run this to check all storage systems at once:

```bash
#!/bin/bash
echo "=== Storage Health Check ==="
echo ""
echo "MongoDB:"
mongosh mongodb://localhost:27017/memsys --quiet --eval "db.serverStatus().ok" || echo "❌ MongoDB not reachable"
echo ""
echo "Elasticsearch:"
curl -s http://localhost:19200/_cluster/health | jq '.status' || echo "❌ ES not reachable"
echo ""
echo "Milvus:"
python3 -c "from pymilvus import connections; connections.connect('localhost', '19530'); print('✅ Connected')" 2>/dev/null || echo "❌ Milvus not reachable"
echo ""
echo "Running full check..."
uv run python src/bootstrap.py src/devops_scripts/data_fix/list_all_storage.py
```

---

Done! Use these commands to inspect your storage systems anytime. 🎉
