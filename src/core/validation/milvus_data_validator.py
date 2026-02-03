"""
Milvus data validator

Validates Milvus data completeness against MongoDB and syncs missing documents.
"""

import time
import traceback
from datetime import timedelta
from typing import Set, List, Dict, Any

from core.observation.logger import get_logger
from core.di.utils import get_bean_by_type
from common_utils.datetime_utils import get_now_with_timezone
from .data_sync_validator import DataSyncValidator, SyncResult

logger = get_logger(__name__)


async def validate_milvus_data(doc_type: str, days: int = 7) -> SyncResult:
    """
    Validate Milvus data completeness for a document type

    Args:
        doc_type: Document type - "episodic_memory", "event_log", or "foresight"
        days: Check documents from last N days (0 = all documents)

    Returns:
        SyncResult with validation and sync statistics
    """
    start_time = time.time()

    try:
        # Route to specific validator based on doc_type
        if doc_type == "episodic_memory":
            result = await _validate_episodic_memory(days)
        elif doc_type == "event_log":
            result = await _validate_event_log(days)
        elif doc_type == "foresight":
            result = await _validate_foresight(days)
        else:
            raise ValueError(f"Unsupported document type: {doc_type}")

        # Update elapsed time
        result.elapsed_time = time.time() - start_time
        return result

    except Exception as e:
        logger.error(
            "Failed to validate Milvus data for %s: %s", doc_type, e, exc_info=True
        )
        # Return error result
        return SyncResult(
            doc_type=doc_type,
            target="milvus",
            total_checked=0,
            missing_count=0,
            synced_count=0,
            error_count=1,
            elapsed_time=time.time() - start_time,
        )


async def _validate_episodic_memory(days: int) -> SyncResult:
    """Validate episodic memory documents"""
    from infra_layer.adapters.out.persistence.repository.episodic_memory_raw_repository import (
        EpisodicMemoryRawRepository,
    )
    from infra_layer.adapters.out.search.milvus.converter.episodic_memory_milvus_converter import (
        EpisodicMemoryMilvusConverter,
    )
    from infra_layer.adapters.out.search.milvus.memory.episodic_memory_collection import (
        EpisodicMemoryCollection,
    )

    mongo_repo = get_bean_by_type(EpisodicMemoryRawRepository)
    collection = EpisodicMemoryCollection.async_collection()

    return await _validate_and_sync(
        doc_type="episodic_memory",
        mongo_repo=mongo_repo,
        collection=collection,
        converter_class=EpisodicMemoryMilvusConverter,
        days=days,
    )


async def _validate_event_log(days: int) -> SyncResult:
    """Validate event log documents"""
    from infra_layer.adapters.out.persistence.repository.event_log_record_raw_repository import (
        EventLogRecordRawRepository,
    )
    from infra_layer.adapters.out.search.milvus.converter.event_log_milvus_converter import (
        EventLogMilvusConverter,
    )
    from infra_layer.adapters.out.search.milvus.memory.event_log_collection import (
        EventLogCollection,
    )

    mongo_repo = get_bean_by_type(EventLogRecordRawRepository)
    collection = EventLogCollection.async_collection()

    return await _validate_and_sync(
        doc_type="event_log",
        mongo_repo=mongo_repo,
        collection=collection,
        converter_class=EventLogMilvusConverter,
        days=days,
    )


async def _validate_foresight(days: int) -> SyncResult:
    """Validate foresight documents"""
    from infra_layer.adapters.out.persistence.repository.foresight_record_repository import (
        ForesightRecordRawRepository,
    )
    from infra_layer.adapters.out.search.milvus.converter.foresight_milvus_converter import (
        ForesightMilvusConverter,
    )
    from infra_layer.adapters.out.search.milvus.memory.foresight_collection import (
        ForesightCollection,
    )

    mongo_repo = get_bean_by_type(ForesightRecordRawRepository)
    collection = ForesightCollection.async_collection()

    return await _validate_and_sync(
        doc_type="foresight",
        mongo_repo=mongo_repo,
        collection=collection,
        converter_class=ForesightMilvusConverter,
        days=days,
    )


async def _validate_and_sync(
    doc_type: str,
    mongo_repo: Any,
    collection: Any,
    converter_class: Any,
    days: int,
) -> SyncResult:
    """
    Common validation and sync logic

    Args:
        doc_type: Document type name
        mongo_repo: MongoDB repository
        collection: Milvus collection
        converter_class: Converter class with from_mongo method
        days: Days to check (0 = all)

    Returns:
        SyncResult
    """
    try:
        # Step 1: Get MongoDB IDs
        mongo_ids = await _get_mongo_ids(mongo_repo, days)
        logger.info(
            "Found %d MongoDB documents for %s", len(mongo_ids), doc_type
        )

        # Step 2: Get Milvus IDs
        milvus_ids = await _get_milvus_ids(collection, days)
        logger.info(
            "Found %d Milvus documents for %s", len(milvus_ids), doc_type
        )

        # Step 3: Find missing IDs
        missing_ids = DataSyncValidator.find_missing_ids(mongo_ids, milvus_ids)

        if not missing_ids:
            # No missing data - success
            return SyncResult(
                doc_type=doc_type,
                target="milvus",
                total_checked=len(mongo_ids),
                missing_count=0,
                synced_count=0,
                error_count=0,
                elapsed_time=0.0,  # Will be updated by caller
            )

        # Step 4: Sync missing documents
        logger.warning(
            "Found %d missing documents for %s, starting sync...",
            len(missing_ids),
            doc_type,
        )

        synced_count, error_count = await _sync_missing_documents(
            mongo_repo=mongo_repo,
            collection=collection,
            converter_class=converter_class,
            missing_ids=missing_ids,
            doc_type=doc_type,
        )

        return SyncResult(
            doc_type=doc_type,
            target="milvus",
            total_checked=len(mongo_ids),
            missing_count=len(missing_ids),
            synced_count=synced_count,
            error_count=error_count,
            elapsed_time=0.0,  # Will be updated by caller
        )

    except Exception as e:
        logger.error(
            "Error during validation and sync for %s: %s",
            doc_type,
            e,
            exc_info=True,
        )
        return SyncResult(
            doc_type=doc_type,
            target="milvus",
            total_checked=0,
            missing_count=0,
            synced_count=0,
            error_count=1,
            elapsed_time=0.0,
        )


async def _get_mongo_ids(mongo_repo: Any, days: int) -> Set[str]:
    """
    Get MongoDB document IDs

    Args:
        mongo_repo: MongoDB repository
        days: Days to look back (0 = all documents)

    Returns:
        Set of document IDs as strings
    """
    # Build query filter
    query_filter: Dict[str, Any] = {}

    if days > 0:
        # Recent documents only
        now = get_now_with_timezone()
        start_time = now - timedelta(days=days)
        query_filter = {"created_at": {"$gte": start_time}}
        logger.info("Fetching MongoDB IDs from last %d days", days)
    else:
        # All documents (full database)
        logger.info("Fetching ALL MongoDB IDs (full database)")

    # Fetch only IDs (projection for efficiency)
    cursor = mongo_repo.model.find(query_filter, projection={"_id": 1})
    docs = await cursor.to_list(length=None)

    return {str(doc.id) for doc in docs}


async def _get_milvus_ids(collection: Any, days: int) -> Set[str]:
    """
    Get Milvus document IDs

    Args:
        collection: Milvus collection
        days: Days to look back (0 = all documents)

    Returns:
        Set of document IDs as strings
    """
    if days > 0:
        # Recent documents only - use time filter
        now = get_now_with_timezone()
        start_time = now - timedelta(days=days)
        start_timestamp = int(start_time.timestamp())

        # NOTE: Assumes collection has 'created_at' field
        expr = f"created_at >= {start_timestamp}"
        logger.info("Fetching Milvus IDs from last %d days", days)

        results = await collection.query(expr=expr, output_fields=["id"])
    else:
        # All documents (full database)
        logger.info("Fetching ALL Milvus IDs (full database)")

        # Query without filter to get all documents
        # Empty expression matches all
        results = await collection.query(expr="", output_fields=["id"])

    return {str(result["id"]) for result in results}


async def _sync_missing_documents(
    mongo_repo: Any,
    collection: Any,
    converter_class: Any,
    missing_ids: Set[str],
    doc_type: str,
    batch_size: int = 500,
) -> tuple[int, int]:
    """
    Sync missing documents to Milvus

    Args:
        mongo_repo: MongoDB repository
        collection: Milvus collection
        converter_class: Converter class
        missing_ids: Set of missing document IDs
        doc_type: Document type name
        batch_size: Batch size for sync operations

    Returns:
        Tuple of (synced_count, error_count)
    """
    synced_count = 0
    error_count = 0

    # Convert set to list for batch processing
    missing_ids_list = list(missing_ids)

    # Process in batches
    for i in range(0, len(missing_ids_list), batch_size):
        batch_ids = missing_ids_list[i : i + batch_size]

        try:
            # Fetch documents from MongoDB
            # Convert ObjectId strings to ObjectId for query
            from bson import ObjectId

            object_ids = [ObjectId(id_str) for id_str in batch_ids]

            query = mongo_repo.model.find({"_id": {"$in": object_ids}})
            mongo_docs = await query.to_list(length=None)

            if not mongo_docs:
                logger.warning(
                    "No documents found in MongoDB for batch %d-%d",
                    i,
                    i + len(batch_ids),
                )
                error_count += len(batch_ids)
                continue

            # Convert to Milvus entities
            milvus_entities: List[Dict[str, Any]] = []
            batch_errors = 0

            for mongo_doc in mongo_docs:
                try:
                    # Convert individual document
                    milvus_entity = converter_class.from_mongo(mongo_doc)

                    # Validate required fields
                    if not milvus_entity.get("id"):
                        logger.warning(
                            "Document missing id field, skipping: %s", mongo_doc.id
                        )
                        batch_errors += 1
                        continue

                    if not milvus_entity.get("vector"):
                        logger.warning(
                            "Document missing vector field, skipping: id=%s",
                            milvus_entity.get("id"),
                        )
                        batch_errors += 1
                        continue

                    milvus_entities.append(milvus_entity)

                except Exception as e:
                    logger.error(
                        "Failed to convert document: id=%s, error=%s",
                        getattr(mongo_doc, "id", "unknown"),
                        e,
                    )
                    batch_errors += 1
                    continue

            # Bulk insert into Milvus
            if milvus_entities:
                try:
                    await collection.insert(milvus_entities)
                    inserted_count = len(milvus_entities)
                    synced_count += inserted_count
                    logger.info(
                        "Batch %d-%d: Synced %d documents for %s",
                        i,
                        i + len(batch_ids),
                        inserted_count,
                        doc_type,
                    )
                except Exception as e:
                    logger.error(
                        "Bulk insert to Milvus failed for batch %d-%d: %s",
                        i,
                        i + len(batch_ids),
                        e,
                    )
                    traceback.print_exc()
                    error_count += len(milvus_entities)

            error_count += batch_errors

        except Exception as e:
            logger.error(
                "Error processing batch %d-%d: %s", i, i + len(batch_ids), e
            )
            traceback.print_exc()
            error_count += len(batch_ids)

    # Flush collection to ensure data persistence
    try:
        await collection.flush()
        logger.info("Milvus collection flush completed for %s", doc_type)
    except Exception as e:
        logger.warning("Milvus collection flush failed for %s: %s", doc_type, e)

    return synced_count, error_count
