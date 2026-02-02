"""
List all Elasticsearch indices with document counts

Usage:
    uv run python src/bootstrap.py src/devops_scripts/data_fix/list_es_indices.py
"""

import asyncio
from elasticsearch import AsyncElasticsearch

from core.observation.logger import get_logger

logger = get_logger(__name__)


async def list_es_indices() -> None:
    """List all Elasticsearch indices with details"""
    client = None
    try:
        # Connect to Elasticsearch
        client = AsyncElasticsearch(
            hosts=["http://localhost:19200"],
            verify_certs=False
        )

        logger.info("=" * 100)
        logger.info("📊 Elasticsearch Indices")
        logger.info("=" * 100)

        # Get all indices using cat API
        indices = await client.cat.indices(format="json")

        if not indices:
            logger.info("No indices found.")
            return

        logger.info(f"Found {len(indices)} index/indices:\n")

        # Print table header
        print(f"{'Index Name':<50} {'Docs Count':<15} {'Store Size':<15} {'Health':<10}")
        print("-" * 90)

        # Filter and sort indices (exclude system indices starting with .)
        filtered_indices = [idx for idx in indices if not idx['index'].startswith('.')]
        sorted_indices = sorted(filtered_indices, key=lambda x: x['index'])

        for idx in sorted_indices:
            index_name = idx['index']
            docs_count = idx.get('docs.count', '0')
            store_size = idx.get('store.size', '0b')
            health = idx.get('health', 'unknown')

            # Format docs count with commas
            try:
                docs_count_formatted = f"{int(docs_count):,}"
            except:
                docs_count_formatted = docs_count

            print(f"{index_name:<50} {docs_count_formatted:<15} {store_size:<15} {health:<10}")

        logger.info("\n" + "=" * 100)

        # Show summary by memory type
        logger.info("\n📈 Summary by Memory Type:")
        memory_types = {
            'episodic-memory': 0,
            'event-log': 0,
            'foresight': 0
        }

        for idx in sorted_indices:
            index_name = idx['index']
            docs_count = int(idx.get('docs.count', '0'))

            if 'episodic-memory' in index_name or 'episodic_memory' in index_name:
                memory_types['episodic-memory'] += docs_count
            elif 'event-log' in index_name or 'event_log' in index_name:
                memory_types['event-log'] += docs_count
            elif 'foresight' in index_name:
                memory_types['foresight'] += docs_count

        for mem_type, count in memory_types.items():
            if count > 0:
                logger.info(f"  {mem_type}: {count:,} documents")

        logger.info("=" * 100)

    except Exception as e:
        logger.error(f"Failed to list Elasticsearch indices: {e}")
        raise
    finally:
        if client:
            await client.close()


if __name__ == "__main__":
    asyncio.run(list_es_indices())
