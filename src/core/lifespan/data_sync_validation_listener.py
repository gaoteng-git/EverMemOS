"""
Data sync validation listener

Automatically validates and syncs Milvus data on application startup.
"""

import os
import asyncio

from core.lifespan.lifespan_factory import AppReadyListener
from core.di.decorators import component
from core.observation.logger import get_logger
from core.validation.data_sync_validator import SyncResult

logger = get_logger(__name__)


@component("data_sync_validation_listener")
class DataSyncValidationListener(AppReadyListener):
    """Validates and syncs Milvus data on application startup"""

    def on_app_ready(self) -> None:
        """Called after all lifespan providers have started"""
        # Check if startup sync is enabled
        enabled = os.getenv("STARTUP_SYNC_ENABLED", "true").lower() == "true"
        if not enabled:
            logger.info("Startup data sync is disabled (STARTUP_SYNC_ENABLED=false)")
            return

        # Get configuration
        days = int(os.getenv("STARTUP_SYNC_DAYS", "7"))
        check_milvus = os.getenv("STARTUP_SYNC_MILVUS", "true").lower() == "true"

        # Skip if Milvus validation is disabled
        if not check_milvus:
            logger.info("Milvus validation is disabled (STARTUP_SYNC_MILVUS=false)")
            return

        # Log appropriate message based on validation mode
        if days == 0:
            logger.warning(
                "🔥 Starting FULL DATABASE validation (all documents) - "
                "this may take several minutes. milvus=true"
            )
        else:
            logger.info(
                "Starting data sync validation (last %d days, milvus=true)", days
            )

        # Run validation asynchronously (non-blocking)
        asyncio.create_task(self._run_validation(days))

    async def _run_validation(self, days: int) -> None:
        """
        Run validation and sync process

        Args:
            days: Days to check (0 = all documents)
        """
        from core.validation.milvus_data_validator import validate_milvus_data

        doc_types = ["episodic_memory", "event_log", "foresight"]
        all_results = []

        try:
            # Validate Milvus for each document type
            logger.info("Validating Milvus data...")
            for doc_type in doc_types:
                try:
                    result = await validate_milvus_data(doc_type, days)
                    all_results.append(result)
                    self._log_result(result, days)
                except Exception as e:
                    logger.error(
                        "Failed to validate %s: %s", doc_type, e, exc_info=True
                    )

            # Summary
            total_synced = sum(r.synced_count for r in all_results)
            total_errors = sum(r.error_count for r in all_results)
            total_checked = sum(r.total_checked for r in all_results)

            if total_synced > 0:
                if days == 0:
                    logger.warning(
                        "🔥 Full database sync completed: %d documents synced, %d errors "
                        "(scanned %d total documents)",
                        total_synced,
                        total_errors,
                        total_checked,
                    )
                else:
                    logger.warning(
                        "⚠️  Startup sync completed: %d documents synced, %d errors",
                        total_synced,
                        total_errors,
                    )
            else:
                if days == 0:
                    logger.info(
                        "✅ Full database sync completed: All data consistent "
                        "(scanned %d documents)",
                        total_checked,
                    )
                else:
                    logger.info("✅ Startup sync completed: All data consistent")

        except Exception as e:
            logger.error("❌ Startup sync validation failed: %s", e, exc_info=True)

    def _log_result(self, result: SyncResult, days: int) -> None:
        """
        Log sync result

        Args:
            result: Sync result
            days: Days checked (for context in logging)
        """
        if result.synced_count > 0:
            logger.warning(
                "📊 %s (%s): Found %d missing docs, synced %d, errors %d (%.2fs)",
                result.doc_type,
                result.target,
                result.missing_count,
                result.synced_count,
                result.error_count,
                result.elapsed_time,
            )
        elif result.error_count > 0:
            logger.error(
                "❌ %s (%s): Validation failed with %d errors",
                result.doc_type,
                result.target,
                result.error_count,
            )
        else:
            if days == 0:
                logger.info(
                    "✅ %s (%s): All %d docs consistent (full database)",
                    result.doc_type,
                    result.target,
                    result.total_checked,
                )
            else:
                logger.info(
                    "✅ %s (%s): All %d docs consistent",
                    result.doc_type,
                    result.target,
                    result.total_checked,
                )
