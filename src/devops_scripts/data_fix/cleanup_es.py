"""
Clean up Elasticsearch indices by deleting all documents

This script deletes all documents in the specified Elasticsearch indices.
The index structure is preserved, only documents are deleted.

WARNING: This will delete ALL data in the specified indices!

Usage:
    # Clean up all memory indices
    uv run python src/bootstrap.py src/devops_scripts/data_fix/cleanup_es.py --all

    # Clean up specific index
    uv run python src/bootstrap.py src/devops_scripts/data_fix/cleanup_es.py --index episodic-memory
    uv run python src/bootstrap.py src/devops_scripts/data_fix/cleanup_es.py --index event-log
    uv run python src/bootstrap.py src/devops_scripts/data_fix/cleanup_es.py --index foresight
"""

import argparse
import asyncio
from typing import List

from core.observation.logger import get_logger

logger = get_logger(__name__)


async def delete_all_documents(doc_class, index_name: str) -> None:
    """
    Delete all documents in an Elasticsearch index

    Args:
        doc_class: Document class (e.g., EpisodicMemoryDoc)
        index_name: Index name for logging
    """
    try:
        logger.info("=" * 80)
        logger.info("Processing index: %s", index_name)

        # Get ES client (get_connection is not async, don't await it)
        client = doc_class.get_connection()
        actual_index = doc_class.get_index_name()

        logger.info("Actual index name: %s", actual_index)

        # Check if index exists
        exists = await client.indices.exists(index=actual_index)

        if not exists:
            logger.info("Index does not exist: %s", actual_index)
            return

        # Get document count before deletion
        count_response = await client.count(index=actual_index)
        doc_count = count_response["count"]
        logger.info("Current document count: %d", doc_count)

        if doc_count == 0:
            logger.info("Index is already empty: %s", actual_index)
            return

        # Delete all documents using delete_by_query
        logger.info("Deleting all documents from index: %s", actual_index)
        delete_response = await client.delete_by_query(
            index=actual_index,
            body={"query": {"match_all": {}}},
            refresh=True,
        )

        deleted_count = delete_response.get("deleted", 0)
        logger.info("✅ Deleted %d documents from index: %s", deleted_count, actual_index)

        # Verify deletion
        count_response = await client.count(index=actual_index)
        remaining_count = count_response["count"]
        logger.info("Remaining document count: %d", remaining_count)

    except Exception as e:
        logger.error("❌ Failed to clean index %s: %s", index_name, e)
        raise


async def cleanup_es(index_names: List[str]) -> None:
    """
    Clean up specified Elasticsearch indices

    Args:
        index_names: List of index names to clean up
    """
    from infra_layer.adapters.out.search.elasticsearch.memory.episodic_memory import (
        EpisodicMemoryDoc,
    )
    from infra_layer.adapters.out.search.elasticsearch.memory.event_log import (
        EventLogDoc,
    )
    from infra_layer.adapters.out.search.elasticsearch.memory.foresight import (
        ForesightDoc,
    )

    index_map = {
        "episodic-memory": EpisodicMemoryDoc,
        "event-log": EventLogDoc,
        "foresight": ForesightDoc,
    }

    logger.info("🧹 Starting Elasticsearch cleanup...")
    logger.info("Indices to clean: %s", ", ".join(index_names))
    logger.info("=" * 80)

    success_count = 0
    error_count = 0

    for name in index_names:
        if name not in index_map:
            logger.error("❌ Unknown index: %s", name)
            error_count += 1
            continue

        try:
            await delete_all_documents(index_map[name], name)
            success_count += 1
        except Exception as e:
            logger.error("❌ Failed to clean index %s: %s", name, e)
            error_count += 1

    logger.info("=" * 80)
    logger.info("🎉 Cleanup completed!")
    logger.info("Success: %d, Failed: %d", success_count, error_count)


def main(argv: list[str] | None = None) -> int:
    """Command-line entry function"""
    parser = argparse.ArgumentParser(
        description="Clean up Elasticsearch indices by deleting all documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Clean up all memory indices
  %(prog)s --all

  # Clean up specific index
  %(prog)s --index episodic-memory
  %(prog)s --index event-log
  %(prog)s --index foresight

WARNING: This will delete ALL data in the specified indices!
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--all",
        action="store_true",
        help="Clean up all memory indices (episodic-memory, event-log, foresight)",
    )
    group.add_argument(
        "--index",
        "-i",
        help="Specific index to clean up",
        choices=["episodic-memory", "event-log", "foresight"],
    )

    args = parser.parse_args(argv)

    # Determine which indices to clean
    if args.all:
        indices = ["episodic-memory", "event-log", "foresight"]
    else:
        indices = [args.index]

    # Confirm before proceeding
    print("\n⚠️  WARNING: This will DELETE ALL DATA in the following indices:")
    for idx in indices:
        print(f"  - {idx}")
    print("\nAre you sure you want to proceed? (yes/no): ", end="")

    confirmation = input().strip().lower()
    if confirmation != "yes":
        print("❌ Cleanup cancelled.")
        return 1

    # Run cleanup
    asyncio.run(cleanup_es(indices))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
