"""
List all Milvus collections with document counts

Usage:
    uv run python src/bootstrap.py src/devops_scripts/data_fix/list_milvus_collections.py
"""

import asyncio
from pymilvus import connections, utility, Collection

from core.observation.logger import get_logger

logger = get_logger(__name__)


async def list_milvus_collections() -> None:
    """List all Milvus collections with details"""
    try:
        # Connect to Milvus (using default connection settings)
        connections.connect(
            alias="default",
            host="localhost",
            port="19530"
        )

        logger.info("=" * 80)
        logger.info("📊 Milvus Collections")
        logger.info("=" * 80)

        # Get all collection names
        collections = utility.list_collections()

        if not collections:
            logger.info("No collections found.")
            return

        logger.info(f"Found {len(collections)} collection(s):\n")

        # Print table header
        print(f"{'Collection Name':<40} {'Entities':<15} {'Loaded':<10}")
        print("-" * 65)

        for collection_name in sorted(collections):
            try:
                collection = Collection(collection_name)

                # Get entity count
                collection.flush()  # Ensure all data is flushed
                entity_count = collection.num_entities

                # Check if loaded
                is_loaded = "Yes" if utility.load_state(collection_name).name == "Loaded" else "No"

                print(f"{collection_name:<40} {entity_count:<15,} {is_loaded:<10}")

            except Exception as e:
                logger.warning(f"Error getting details for {collection_name}: {e}")
                print(f"{collection_name:<40} {'Error':<15} {'N/A':<10}")

        logger.info("\n" + "=" * 80)

    except Exception as e:
        logger.error(f"Failed to list Milvus collections: {e}")
        raise
    finally:
        try:
            connections.disconnect("default")
        except:
            pass


if __name__ == "__main__":
    asyncio.run(list_milvus_collections())
