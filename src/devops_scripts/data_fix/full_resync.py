"""
Full cleanup and resync script

This script performs a complete cleanup of Milvus and Elasticsearch,
then resyncs all memory data from MongoDB.

WARNING: This will delete ALL data in Milvus and Elasticsearch!

Usage:
    uv run python src/bootstrap.py src/devops_scripts/data_fix/full_resync.py
"""

import asyncio
from core.observation.logger import get_logger

logger = get_logger(__name__)


async def run_full_resync() -> None:
    """
    Run full cleanup and resync for all memory types
    """
    from devops_scripts.data_fix.cleanup_milvus import cleanup_milvus
    from devops_scripts.data_fix.cleanup_es import cleanup_es
    from devops_scripts.data_fix.milvus_sync_episodic_memory_docs import (
        sync_episodic_memory_docs as sync_episodic_milvus,
    )
    from devops_scripts.data_fix.milvus_sync_event_log_docs import (
        sync_event_log_docs as sync_eventlog_milvus,
    )
    from devops_scripts.data_fix.milvus_sync_foresight_docs import (
        sync_foresight_docs as sync_foresight_milvus,
    )
    from devops_scripts.data_fix.es_sync_episodic_memory_docs import (
        sync_episodic_memory_docs as sync_episodic_es,
    )
    from devops_scripts.data_fix.es_sync_event_log_docs import (
        sync_event_log_docs as sync_eventlog_es,
    )
    from devops_scripts.data_fix.es_sync_foresight_docs import (
        sync_foresight_docs as sync_foresight_es,
    )

    logger.info("=" * 80)
    logger.info("🚀 Starting FULL RESYNC")
    logger.info("=" * 80)

    # Step 1: Cleanup Milvus
    logger.info("\n📍 Step 1/7: Cleaning up Milvus collections...")
    try:
        await cleanup_milvus(["episodic_memory", "event_log", "foresight"])
        logger.info("✅ Milvus cleanup completed")
    except Exception as e:
        logger.error("❌ Milvus cleanup failed: %s", e)
        raise

    # Step 2: Cleanup Elasticsearch
    logger.info("\n📍 Step 2/7: Cleaning up Elasticsearch indices...")
    try:
        await cleanup_es(["episodic-memory", "event-log", "foresight"])
        logger.info("✅ Elasticsearch cleanup completed")
    except Exception as e:
        logger.error("❌ Elasticsearch cleanup failed: %s", e)
        raise

    # Step 3: Sync Episodic Memory to Milvus
    logger.info("\n📍 Step 3/7: Syncing Episodic Memory to Milvus...")
    try:
        await sync_episodic_milvus(batch_size=500, limit=None, days=None)
        logger.info("✅ Episodic Memory → Milvus sync completed")
    except Exception as e:
        logger.error("❌ Episodic Memory → Milvus sync failed: %s", e)
        raise

    # Step 4: Sync Episodic Memory to ES
    logger.info("\n📍 Step 4/7: Syncing Episodic Memory to Elasticsearch...")
    try:
        await sync_episodic_es(batch_size=500, limit=None, days=None)
        logger.info("✅ Episodic Memory → ES sync completed")
    except Exception as e:
        logger.error("❌ Episodic Memory → ES sync failed: %s", e)
        raise

    # Step 5: Sync Event Log to Milvus
    logger.info("\n📍 Step 5/7: Syncing Event Log to Milvus...")
    try:
        await sync_eventlog_milvus(batch_size=500, limit=None, days=None)
        logger.info("✅ Event Log → Milvus sync completed")
    except Exception as e:
        logger.error("❌ Event Log → Milvus sync failed: %s", e)
        raise

    # Step 6: Sync Event Log to ES
    logger.info("\n📍 Step 6/7: Syncing Event Log to Elasticsearch...")
    try:
        await sync_eventlog_es(batch_size=500, limit=None, days=None)
        logger.info("✅ Event Log → ES sync completed")
    except Exception as e:
        logger.error("❌ Event Log → ES sync failed: %s", e)
        raise

    # Step 7: Sync Foresight to Milvus
    logger.info("\n📍 Step 7/7: Syncing Foresight to Milvus...")
    try:
        await sync_foresight_milvus(batch_size=500, limit=None, days=None)
        logger.info("✅ Foresight → Milvus sync completed")
    except Exception as e:
        logger.error("❌ Foresight → Milvus sync failed: %s", e)
        raise

    # Step 8: Sync Foresight to ES
    logger.info("\n📍 Step 8/7: Syncing Foresight to Elasticsearch...")
    try:
        await sync_foresight_es(batch_size=500, limit=None, days=None)
        logger.info("✅ Foresight → ES sync completed")
    except Exception as e:
        logger.error("❌ Foresight → ES sync failed: %s", e)
        raise

    logger.info("\n" + "=" * 80)
    logger.info("🎉 FULL RESYNC COMPLETED SUCCESSFULLY!")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_full_resync())
