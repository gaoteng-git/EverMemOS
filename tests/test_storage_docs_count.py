"""
Storage Document Count Test

Connects to MongoDB, Milvus, and Elasticsearch independently and prints
the document/entity count for every collection / index.

Run:
    uv run pytest tests/test_storage_docs_count.py -v -s
"""

import os
import sys
import pytest
import pytest_asyncio
from pathlib import Path

src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


# ---------------------------------------------------------------------------
# MongoDB
# ---------------------------------------------------------------------------

def count_mongodb() -> dict[str, int]:
    """Return {collection_name: doc_count} for all known collections."""
    from dotenv import load_dotenv
    import pymongo

    load_dotenv()

    host = os.getenv("MONGODB_HOST", "localhost")
    port = os.getenv("MONGODB_PORT", "27017")
    username = os.getenv("MONGODB_USERNAME", "")
    password = os.getenv("MONGODB_PASSWORD", "")
    db_name = os.getenv("MONGODB_DATABASE", "memsys")

    if username and password:
        uri = f"mongodb://{username}:{password}@{host}:{port}"
    else:
        uri = f"mongodb://{host}:{port}"

    client = pymongo.MongoClient(uri)
    db = client[db_name]

    # All known collection names from document model Settings.name
    collections = [
        "episodic_memories",
        "event_log_records",
        "foresight_records",
        "core_memories",
        "conversation_metas",
        "conversation_status",
        "user_profiles",
        "group_profiles",
        "group_core_profile_memory",
        "entities",
        "relationships",
        "behavior_histories",
        "memcells",
        "cluster_states",
        "memory_request_logs",
    ]

    counts = {}
    for name in collections:
        try:
            counts[name] = db[name].count_documents({})
        except Exception as e:
            counts[name] = f"ERROR: {e}"

    client.close()
    return counts


# ---------------------------------------------------------------------------
# Milvus
# ---------------------------------------------------------------------------

def count_milvus() -> dict[str, int]:
    """Return {collection_name: entity_count} for all Milvus collections."""
    from pymilvus import connections, utility, Collection

    host = os.getenv("MILVUS_HOST", "localhost")
    port = os.getenv("MILVUS_PORT", "19530")
    user = os.getenv("MILVUS_USER", "")
    password = os.getenv("MILVUS_PASSWORD", "")

    connect_kwargs = {"alias": "default", "host": host, "port": port}
    if user:
        connect_kwargs["user"] = user
        connect_kwargs["password"] = password

    connections.connect(**connect_kwargs)

    counts = {}
    try:
        collection_names = utility.list_collections()
        for name in sorted(collection_names):
            try:
                col = Collection(name)
                col.flush()
                counts[name] = col.num_entities
            except Exception as e:
                counts[name] = f"ERROR: {e}"
    finally:
        connections.disconnect("default")

    return counts


# ---------------------------------------------------------------------------
# Elasticsearch
# ---------------------------------------------------------------------------

async def count_elasticsearch() -> dict[str, int]:
    """Return {index_name: doc_count} for all non-system ES indices."""
    from elasticsearch import AsyncElasticsearch

    es_hosts_str = os.getenv("ES_HOSTS")
    if es_hosts_str:
        hosts = [h.strip() for h in es_hosts_str.split(",")]
    else:
        host = os.getenv("ES_HOST", "localhost")
        port = os.getenv("ES_PORT", "9200")
        hosts = [f"http://{host}:{port}"]

    username = os.getenv("ES_USERNAME")
    password = os.getenv("ES_PASSWORD")
    api_key = os.getenv("ES_API_KEY")

    kwargs: dict = {"hosts": hosts, "verify_certs": False}
    if api_key:
        kwargs["api_key"] = api_key
    elif username and password:
        kwargs["basic_auth"] = (username, password)

    client = AsyncElasticsearch(**kwargs)
    counts = {}
    try:
        indices = await client.cat.indices(format="json")
        for idx in sorted(indices, key=lambda x: x["index"]):
            name = idx["index"]
            if name.startswith("."):
                continue
            try:
                counts[name] = int(idx.get("docs.count", 0))
            except (ValueError, TypeError):
                counts[name] = idx.get("docs.count", "?")
    except Exception as e:
        counts["_error"] = f"ERROR: {e}"
    finally:
        await client.close()

    return counts


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def init_database():
    """Override conftest.py autouse fixture — this test needs no DB init."""
    yield


@pytest.mark.asyncio
async def test_storage_docs_count():
    """Print document counts for MongoDB, Milvus, and Elasticsearch."""
    from dotenv import load_dotenv
    load_dotenv()

    # ---- MongoDB ----
    print("\n" + "=" * 60)
    print("  MongoDB collections")
    print("=" * 60)
    try:
        mongo_counts = count_mongodb()
        total = 0
        for name, count in mongo_counts.items():
            is_int = isinstance(count, int)
            total += count if is_int else 0
            marker = "  " if is_int else "!!"
            print(f"  {marker} {name:<40} {count:>10,}" if is_int else f"  {marker} {name:<40} {count}")
        print(f"  {'TOTAL':<40} {total:>10,}")
    except Exception as e:
        print(f"  !! MongoDB connection failed: {e}")

    # ---- Milvus ----
    print("\n" + "=" * 60)
    print("  Milvus collections")
    print("=" * 60)
    try:
        milvus_counts = count_milvus()
        if not milvus_counts:
            print("  (no collections found)")
        total = 0
        for name, count in milvus_counts.items():
            is_int = isinstance(count, int)
            total += count if is_int else 0
            marker = "  " if is_int else "!!"
            print(f"  {marker} {name:<40} {count:>10,}" if is_int else f"  {marker} {name:<40} {count}")
        if milvus_counts:
            print(f"  {'TOTAL':<40} {total:>10,}")
    except Exception as e:
        print(f"  !! Milvus connection failed: {e}")

    # ---- Elasticsearch ----
    print("\n" + "=" * 60)
    print("  Elasticsearch indices")
    print("=" * 60)
    try:
        es_counts = await count_elasticsearch()
        if not es_counts:
            print("  (no indices found)")
        total = 0
        for name, count in es_counts.items():
            is_int = isinstance(count, int)
            total += count if is_int else 0
            marker = "  " if is_int else "!!"
            print(f"  {marker} {name:<40} {count:>10,}" if is_int else f"  {marker} {name:<40} {count}")
        if es_counts:
            print(f"  {'TOTAL':<40} {total:>10,}")
    except Exception as e:
        print(f"  !! Elasticsearch connection failed: {e}")

    print("\n" + "=" * 60)
