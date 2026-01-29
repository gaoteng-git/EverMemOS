"""
List all storage systems (Milvus + Elasticsearch) with document counts

Usage:
    uv run python src/bootstrap.py src/devops_scripts/data_fix/list_all_storage.py
"""

import asyncio
from pymilvus import connections, utility, Collection
from elasticsearch import AsyncElasticsearch

from core.observation.logger import get_logger

logger = get_logger(__name__)


async def list_milvus() -> dict:
    """List Milvus collections and return counts"""
    collections_info = {}

    try:
        connections.connect(
            alias="default",
            host="localhost",
            port="19530"
        )

        logger.info("=" * 80)
        logger.info("🗄️  MILVUS COLLECTIONS")
        logger.info("=" * 80)

        collections = utility.list_collections()

        if not collections:
            logger.info("No collections found.\n")
            return collections_info

        logger.info(f"Found {len(collections)} collection(s):\n")

        print(f"{'Collection Name':<40} {'Entities':<15} {'Loaded':<10}")
        print("-" * 65)

        for collection_name in sorted(collections):
            try:
                collection = Collection(collection_name)
                collection.flush()
                entity_count = collection.num_entities
                is_loaded = "Yes" if utility.load_state(collection_name).name == "Loaded" else "No"

                print(f"{collection_name:<40} {entity_count:<15,} {is_loaded:<10}")

                # Store for summary
                if 'episodic_memory' in collection_name:
                    collections_info['episodic_memory'] = entity_count
                elif 'event_log' in collection_name:
                    collections_info['event_log'] = entity_count
                elif 'foresight' in collection_name:
                    collections_info['foresight'] = entity_count

            except Exception as e:
                logger.warning(f"Error getting details for {collection_name}: {e}")
                print(f"{collection_name:<40} {'Error':<15} {'N/A':<10}")

        print()

    except Exception as e:
        logger.error(f"Failed to list Milvus collections: {e}")
    finally:
        try:
            connections.disconnect("default")
        except:
            pass

    return collections_info


async def list_elasticsearch() -> dict:
    """List Elasticsearch indices and return counts"""
    indices_info = {}
    client = None

    try:
        client = AsyncElasticsearch(
            hosts=["http://localhost:19200"],
            verify_certs=False
        )

        logger.info("=" * 80)
        logger.info("🔍 ELASTICSEARCH INDICES")
        logger.info("=" * 80)

        indices = await client.cat.indices(format="json")

        if not indices:
            logger.info("No indices found.\n")
            return indices_info

        filtered_indices = [idx for idx in indices if not idx['index'].startswith('.')]
        logger.info(f"Found {len(filtered_indices)} index/indices:\n")

        print(f"{'Index Name':<50} {'Docs Count':<15} {'Store Size':<15} {'Health':<10}")
        print("-" * 90)

        sorted_indices = sorted(filtered_indices, key=lambda x: x['index'])

        for idx in sorted_indices:
            index_name = idx['index']
            docs_count = idx.get('docs.count', '0')
            store_size = idx.get('store.size', '0b')
            health = idx.get('health', 'unknown')

            try:
                docs_count_formatted = f"{int(docs_count):,}"
                docs_count_int = int(docs_count)
            except:
                docs_count_formatted = docs_count
                docs_count_int = 0

            print(f"{index_name:<50} {docs_count_formatted:<15} {store_size:<15} {health:<10}")

            # Store for summary
            if 'episodic-memory' in index_name or 'episodic_memory' in index_name:
                indices_info['episodic_memory'] = indices_info.get('episodic_memory', 0) + docs_count_int
            elif 'event-log' in index_name or 'event_log' in index_name:
                indices_info['event_log'] = indices_info.get('event_log', 0) + docs_count_int
            elif 'foresight' in index_name:
                indices_info['foresight'] = indices_info.get('foresight', 0) + docs_count_int

        print()

    except Exception as e:
        logger.error(f"Failed to list Elasticsearch indices: {e}")
    finally:
        if client:
            await client.close()

    return indices_info


async def main():
    """Main function to list all storage systems"""
    logger.info("\n" + "=" * 80)
    logger.info("📊 STORAGE SYSTEMS OVERVIEW")
    logger.info("=" * 80)
    logger.info("")

    # List Milvus
    milvus_info = await list_milvus()

    # List Elasticsearch
    es_info = await list_elasticsearch()

    # Print summary comparison
    logger.info("=" * 80)
    logger.info("📈 SUMMARY COMPARISON")
    logger.info("=" * 80)
    logger.info("")

    print(f"{'Memory Type':<20} {'Milvus':<20} {'Elasticsearch':<20}")
    print("-" * 60)

    memory_types = ['episodic_memory', 'event_log', 'foresight']
    for mem_type in memory_types:
        milvus_count = milvus_info.get(mem_type, 0)
        es_count = es_info.get(mem_type, 0)

        # Format with display names
        display_name = mem_type.replace('_', ' ').title()

        milvus_str = f"{milvus_count:,}" if milvus_count > 0 else "-"
        es_str = f"{es_count:,}" if es_count > 0 else "-"

        print(f"{display_name:<20} {milvus_str:<20} {es_str:<20}")

    logger.info("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
