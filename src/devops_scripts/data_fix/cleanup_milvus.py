"""
Clean up Milvus collections by dropping and recreating them

This script drops the specified Milvus collections and recreates them with fresh schema.
WARNING: This will delete ALL data in the specified collections!

Usage:
    # Clean up all memory collections
    uv run python src/bootstrap.py src/devops_scripts/data_fix/cleanup_milvus.py --all

    # Clean up specific collection
    uv run python src/bootstrap.py src/devops_scripts/data_fix/cleanup_milvus.py --collection episodic_memory
    uv run python src/bootstrap.py src/devops_scripts/data_fix/cleanup_milvus.py --collection event_log
    uv run python src/bootstrap.py src/devops_scripts/data_fix/cleanup_milvus.py --collection foresight
"""

import argparse
import asyncio
from typing import List

from core.observation.logger import get_logger
from pymilvus import utility

logger = get_logger(__name__)


async def drop_and_recreate_collection(collection_class, collection_name: str) -> None:
    """
    Drop and recreate a Milvus collection

    Args:
        collection_class: Collection class (e.g., EpisodicMemoryCollection)
        collection_name: Collection name for logging
    """
    try:
        # Get the async collection
        collection = collection_class.async_collection()
        alias_name = collection.collection.name

        logger.info("=" * 80)
        logger.info("Processing collection: %s (alias: %s)", collection_name, alias_name)

        # Get the real collection name (with timestamp suffix)
        conn = collection.collection._get_connection()
        collection_desc = conn.describe_collection(alias_name)
        real_name = collection_desc.get("collection_name", alias_name)

        logger.info("Real collection name: %s", real_name)

        # Use default connection alias
        using = "default"

        # Check if real collection exists
        if utility.has_collection(real_name, using=using):
            logger.info("Dropping collection: %s", real_name)
            utility.drop_collection(real_name, using=using)
            logger.info("✅ Collection dropped: %s", real_name)
        else:
            logger.info("Collection does not exist: %s", real_name)

        # Clear cached collection instances (important!)
        logger.info("Clearing cached collection instances")
        collection_class._collection_instance = None
        collection_class._async_collection_instance = None

        # Recreate collection by instantiating and calling ensure_all
        logger.info("Recreating collection: %s", collection_name)
        new_collection = collection_class()
        new_collection.ensure_all()
        logger.info("✅ Collection recreated: %s", collection_name)

    except Exception as e:
        logger.error("❌ Failed to process collection %s: %s", collection_name, e)
        raise


async def cleanup_milvus(collection_names: List[str]) -> None:
    """
    Clean up specified Milvus collections

    Args:
        collection_names: List of collection names to clean up
    """
    from infra_layer.adapters.out.search.milvus.memory.episodic_memory_collection import (
        EpisodicMemoryCollection,
    )
    from infra_layer.adapters.out.search.milvus.memory.event_log_collection import (
        EventLogCollection,
    )
    from infra_layer.adapters.out.search.milvus.memory.foresight_collection import (
        ForesightCollection,
    )

    collection_map = {
        "episodic_memory": EpisodicMemoryCollection,
        "event_log": EventLogCollection,
        "foresight": ForesightCollection,
    }

    logger.info("🧹 Starting Milvus cleanup...")
    logger.info("Collections to clean: %s", ", ".join(collection_names))
    logger.info("=" * 80)

    success_count = 0
    error_count = 0

    for name in collection_names:
        if name not in collection_map:
            logger.error("❌ Unknown collection: %s", name)
            error_count += 1
            continue

        try:
            await drop_and_recreate_collection(collection_map[name], name)
            success_count += 1
        except Exception as e:
            logger.error("❌ Failed to clean collection %s: %s", name, e)
            error_count += 1

    logger.info("=" * 80)
    logger.info("🎉 Cleanup completed!")
    logger.info("Success: %d, Failed: %d", success_count, error_count)


def main(argv: list[str] | None = None) -> int:
    """Command-line entry function"""
    parser = argparse.ArgumentParser(
        description="Clean up Milvus collections by dropping and recreating them",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Clean up all memory collections
  %(prog)s --all

  # Clean up specific collection
  %(prog)s --collection episodic_memory
  %(prog)s --collection event_log
  %(prog)s --collection foresight

WARNING: This will delete ALL data in the specified collections!
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--all",
        action="store_true",
        help="Clean up all memory collections (episodic_memory, event_log, foresight)",
    )
    group.add_argument(
        "--collection",
        "-c",
        help="Specific collection to clean up",
        choices=["episodic_memory", "event_log", "foresight"],
    )

    args = parser.parse_args(argv)

    # Determine which collections to clean
    if args.all:
        collections = ["episodic_memory", "event_log", "foresight"]
    else:
        collections = [args.collection]

    # Confirm before proceeding
    print("\n⚠️  WARNING: This will DELETE ALL DATA in the following collections:")
    for col in collections:
        print(f"  - {col}")
    print("\nAre you sure you want to proceed? (yes/no): ", end="")

    confirmation = input().strip().lower()
    if confirmation != "yes":
        print("❌ Cleanup cancelled.")
        return 1

    # Run cleanup
    asyncio.run(cleanup_milvus(collections))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
