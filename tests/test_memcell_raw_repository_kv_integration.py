#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test KV-Storage integration in MemCellRawRepository

This test file focuses on testing the KV-Storage dual-write and validation
functionality added to the MemCellRawRepository. It tests:

1. Dual-write operations (append, update, delete)
2. Read validation against KV-Storage
3. Graceful degradation when KV-Storage is unavailable
4. Batch operations with KV-Storage
5. Data consistency validation

Modified functions being tested:
- get_by_event_id
- get_by_event_ids
- append_memcell
- update_by_event_id
- delete_by_event_id
- find_by_user_id
- find_by_user_and_time_range
- find_by_group_id
- find_by_time_range
- find_by_participants
- search_by_keywords
- delete_by_user_id
- delete_by_time_range
- get_latest_by_user
"""

import asyncio
import pytest
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

# Mark all test functions in this module as asyncio tests
pytestmark = pytest.mark.asyncio

from common_utils.datetime_utils import get_now_with_timezone
from core.di import get_bean_by_type
from core.observation.logger import get_logger
from infra_layer.adapters.out.persistence.document.memory.memcell import (
    DataTypeEnum,
    MemCell,
)
from infra_layer.adapters.out.persistence.repository.memcell_raw_repository import (
    MemCellRawRepository,
)

logger = get_logger(__name__)


# ==================== Test Helpers ====================


def create_mock_kv_storage():
    """Create a mock KV-Storage instance with standard methods"""
    mock_kv = MagicMock()
    mock_kv.get = AsyncMock(return_value=None)
    mock_kv.put = AsyncMock(return_value=True)
    mock_kv.delete = AsyncMock(return_value=True)
    mock_kv.batch_get = AsyncMock(return_value={})
    mock_kv.batch_delete = AsyncMock(return_value=0)
    return mock_kv


async def create_test_memcell(user_id: str, summary: str = "Test memory") -> MemCell:
    """Helper function to create a test MemCell"""
    now = get_now_with_timezone()
    return MemCell(
        user_id=user_id,
        timestamp=now,
        summary=summary,
        type=DataTypeEnum.CONVERSATION,
        keywords=["test"],
        participants=["User A", "User B"],
    )


# ==================== Test Cases ====================


async def test_append_memcell_with_kv_dual_write():
    """
    Test append_memcell performs dual-write to both MongoDB and KV-Storage

    Validates:
    - Data is written to MongoDB (primary)
    - Data is also written to KV-Storage (secondary)
    - KV-Storage receives correctly serialized data
    """
    logger.info("Starting test: append_memcell with KV dual-write...")

    repo = get_bean_by_type(MemCellRawRepository)
    user_id = "test_kv_append_001"

    try:
        # Clean up
        await repo.delete_by_user_id(user_id)

        # Create test data
        memcell = await create_test_memcell(user_id, "Test KV dual-write")

        # Mock KV-Storage
        mock_kv = create_mock_kv_storage()
        original_kv = repo._kv_storage
        repo._kv_storage = mock_kv

        try:
            # Execute append
            created = await repo.append_memcell(memcell)
            assert created is not None

            # Verify MongoDB write
            result = await repo.get_by_event_id(str(created.id))
            assert result is not None
            assert result.summary == "Test KV dual-write"

            # Verify KV-Storage write was called
            mock_kv.put.assert_called_once()
            call_args = mock_kv.put.call_args
            assert call_args.kwargs["key"] == str(created.id)
            assert "Test KV dual-write" in call_args.kwargs["value"]

            logger.info("✅ Verified dual-write to MongoDB and KV-Storage")

        finally:
            # Restore original KV-Storage
            repo._kv_storage = original_kv

        # Clean up
        await repo.delete_by_user_id(user_id)
        logger.info("✅ Test append_memcell with KV dual-write passed")

    except Exception as e:
        logger.error("❌ Test failed: %s", e)
        raise


async def test_update_memcell_with_kv_dual_write():
    """
    Test update_by_event_id performs dual-write to both MongoDB and KV-Storage

    Validates:
    - Updated data is written to MongoDB
    - Updated data is also written to KV-Storage
    """
    logger.info("Starting test: update_memcell with KV dual-write...")

    repo = get_bean_by_type(MemCellRawRepository)
    user_id = "test_kv_update_001"

    try:
        # Clean up
        await repo.delete_by_user_id(user_id)

        # Create test data
        memcell = await create_test_memcell(user_id, "Original summary")
        created = await repo.append_memcell(memcell)
        event_id = str(created.id)

        # Mock KV-Storage
        mock_kv = create_mock_kv_storage()
        original_kv = repo._kv_storage
        repo._kv_storage = mock_kv

        try:
            # Execute update
            update_data = {"summary": "Updated summary"}
            updated = await repo.update_by_event_id(event_id, update_data)
            assert updated is not None

            # Verify MongoDB update
            assert updated.summary == "Updated summary"

            # Verify KV-Storage update was called
            mock_kv.put.assert_called_once()
            call_args = mock_kv.put.call_args
            assert call_args.kwargs["key"] == event_id
            assert "Updated summary" in call_args.kwargs["value"]

            logger.info("✅ Verified dual-write update to MongoDB and KV-Storage")

        finally:
            # Restore original KV-Storage
            repo._kv_storage = original_kv

        # Clean up
        await repo.delete_by_user_id(user_id)
        logger.info("✅ Test update_memcell with KV dual-write passed")

    except Exception as e:
        logger.error("❌ Test failed: %s", e)
        raise


async def test_delete_memcell_with_kv_dual_delete():
    """
    Test delete_by_event_id performs dual-delete from both MongoDB and KV-Storage

    Validates:
    - Data is deleted from MongoDB
    - Data is also deleted from KV-Storage
    """
    logger.info("Starting test: delete_memcell with KV dual-delete...")

    repo = get_bean_by_type(MemCellRawRepository)
    user_id = "test_kv_delete_001"

    try:
        # Clean up
        await repo.delete_by_user_id(user_id)

        # Create test data
        memcell = await create_test_memcell(user_id, "To be deleted")
        created = await repo.append_memcell(memcell)
        event_id = str(created.id)

        # Mock KV-Storage
        mock_kv = create_mock_kv_storage()
        original_kv = repo._kv_storage
        repo._kv_storage = mock_kv

        try:
            # Execute delete
            deleted = await repo.delete_by_event_id(event_id)
            assert deleted is True

            # Verify MongoDB delete
            result = await repo.get_by_event_id(event_id)
            assert result is None

            # Verify KV-Storage delete was called
            mock_kv.delete.assert_called_once()
            call_args = mock_kv.delete.call_args
            assert call_args.kwargs["key"] == event_id

            logger.info("✅ Verified dual-delete from MongoDB and KV-Storage")

        finally:
            # Restore original KV-Storage
            repo._kv_storage = original_kv

        logger.info("✅ Test delete_memcell with KV dual-delete passed")

    except Exception as e:
        logger.error("❌ Test failed: %s", e)
        raise


async def test_get_by_event_id_with_kv_validation():
    """
    Test get_by_event_id performs validation against KV-Storage

    Validates:
    - Data is read from MongoDB (authoritative)
    - Data is validated against KV-Storage
    - MongoDB data is returned regardless of validation result
    """
    logger.info("Starting test: get_by_event_id with KV validation...")

    repo = get_bean_by_type(MemCellRawRepository)
    user_id = "test_kv_get_001"

    try:
        # Clean up
        await repo.delete_by_user_id(user_id)

        # Create test data
        memcell = await create_test_memcell(user_id, "Test validation")
        created = await repo.append_memcell(memcell)
        event_id = str(created.id)

        # Mock KV-Storage with matching data
        mock_kv = create_mock_kv_storage()
        mock_kv.get = AsyncMock(
            return_value=created.model_dump_json(by_alias=True, exclude_none=False)
        )

        original_kv = repo._kv_storage
        repo._kv_storage = mock_kv

        try:
            # Execute get with validation
            result = await repo.get_by_event_id(event_id)
            assert result is not None
            assert result.summary == "Test validation"

            # Verify KV-Storage get was called for validation
            mock_kv.get.assert_called_once()
            call_args = mock_kv.get.call_args
            assert call_args.kwargs["key"] == event_id

            logger.info("✅ Verified read from MongoDB with KV validation")

        finally:
            # Restore original KV-Storage
            repo._kv_storage = original_kv

        # Clean up
        await repo.delete_by_user_id(user_id)
        logger.info("✅ Test get_by_event_id with KV validation passed")

    except Exception as e:
        logger.error("❌ Test failed: %s", e)
        raise


async def test_get_by_event_ids_with_kv_batch_validation():
    """
    Test get_by_event_ids performs batch validation against KV-Storage

    Validates:
    - Multiple records are read from MongoDB
    - Batch validation is performed against KV-Storage
    - MongoDB data is returned
    """
    logger.info("Starting test: get_by_event_ids with KV batch validation...")

    repo = get_bean_by_type(MemCellRawRepository)
    user_id = "test_kv_batch_001"

    try:
        # Clean up
        await repo.delete_by_user_id(user_id)

        # Create multiple test records
        created_memcells = []
        for i in range(3):
            memcell = await create_test_memcell(user_id, f"Test batch {i+1}")
            created = await repo.append_memcell(memcell)
            created_memcells.append(created)

        event_ids = [str(mc.id) for mc in created_memcells]

        # Mock KV-Storage with matching batch data
        mock_kv = create_mock_kv_storage()
        kv_data = {
            event_id: mc.model_dump_json(by_alias=True, exclude_none=False)
            for event_id, mc in zip(event_ids, created_memcells)
        }
        mock_kv.batch_get = AsyncMock(return_value=kv_data)

        original_kv = repo._kv_storage
        repo._kv_storage = mock_kv

        try:
            # Execute batch get with validation
            results = await repo.get_by_event_ids(event_ids)
            assert len(results) == 3

            # Verify all records returned
            for event_id in event_ids:
                assert event_id in results

            # Verify KV-Storage batch_get was called for validation
            mock_kv.batch_get.assert_called_once()
            call_args = mock_kv.batch_get.call_args
            assert set(call_args.kwargs["keys"]) == set(event_ids)

            logger.info("✅ Verified batch read from MongoDB with KV validation")

        finally:
            # Restore original KV-Storage
            repo._kv_storage = original_kv

        # Clean up
        await repo.delete_by_user_id(user_id)
        logger.info("✅ Test get_by_event_ids with KV batch validation passed")

    except Exception as e:
        logger.error("❌ Test failed: %s", e)
        raise


async def test_find_by_user_id_with_kv_validation():
    """
    Test find_by_user_id performs batch validation against KV-Storage

    Validates:
    - Query results are validated against KV-Storage
    - Batch validation is used for efficiency
    """
    logger.info("Starting test: find_by_user_id with KV validation...")

    repo = get_bean_by_type(MemCellRawRepository)
    user_id = "test_kv_find_001"

    try:
        # Clean up
        await repo.delete_by_user_id(user_id)

        # Create test data
        created_memcells = []
        for i in range(3):
            memcell = await create_test_memcell(user_id, f"Test find {i+1}")
            created = await repo.append_memcell(memcell)
            created_memcells.append(created)

        # Mock KV-Storage
        mock_kv = create_mock_kv_storage()
        kv_data = {
            str(mc.id): mc.model_dump_json(by_alias=True, exclude_none=False)
            for mc in created_memcells
        }
        mock_kv.batch_get = AsyncMock(return_value=kv_data)

        original_kv = repo._kv_storage
        repo._kv_storage = mock_kv

        try:
            # Execute find with validation
            results = await repo.find_by_user_id(user_id)
            assert len(results) == 3

            # Verify KV-Storage batch validation was called
            mock_kv.batch_get.assert_called_once()

            logger.info("✅ Verified find_by_user_id with KV validation")

        finally:
            # Restore original KV-Storage
            repo._kv_storage = original_kv

        # Clean up
        await repo.delete_by_user_id(user_id)
        logger.info("✅ Test find_by_user_id with KV validation passed")

    except Exception as e:
        logger.error("❌ Test failed: %s", e)
        raise


async def test_graceful_degradation_when_kv_unavailable():
    """
    Test repository continues to work when KV-Storage is unavailable

    Validates:
    - Write operations succeed even if KV-Storage fails
    - Read operations succeed even if KV-Storage fails
    - No exceptions are raised to the caller
    """
    logger.info("Starting test: graceful degradation when KV unavailable...")

    repo = get_bean_by_type(MemCellRawRepository)
    user_id = "test_kv_degradation_001"

    try:
        # Clean up
        await repo.delete_by_user_id(user_id)

        # Mock KV-Storage to always fail
        mock_kv = create_mock_kv_storage()
        mock_kv.put = AsyncMock(side_effect=Exception("KV-Storage unavailable"))
        mock_kv.get = AsyncMock(side_effect=Exception("KV-Storage unavailable"))
        mock_kv.delete = AsyncMock(side_effect=Exception("KV-Storage unavailable"))
        mock_kv.batch_get = AsyncMock(side_effect=Exception("KV-Storage unavailable"))

        original_kv = repo._kv_storage
        repo._kv_storage = mock_kv

        try:
            # Test append still works
            memcell = await create_test_memcell(user_id, "Test degradation")
            created = await repo.append_memcell(memcell)
            assert created is not None
            event_id = str(created.id)

            logger.info("✅ Append succeeded despite KV-Storage failure")

            # Test get still works
            result = await repo.get_by_event_id(event_id)
            assert result is not None
            assert result.summary == "Test degradation"

            logger.info("✅ Get succeeded despite KV-Storage failure")

            # Test update still works
            updated = await repo.update_by_event_id(
                event_id, {"summary": "Updated despite failure"}
            )
            assert updated is not None
            assert updated.summary == "Updated despite failure"

            logger.info("✅ Update succeeded despite KV-Storage failure")

            # Test delete still works
            deleted = await repo.delete_by_event_id(event_id)
            assert deleted is True

            logger.info("✅ Delete succeeded despite KV-Storage failure")

            # Test query still works
            memcell2 = await create_test_memcell(user_id, "Test query")
            await repo.append_memcell(memcell2)

            results = await repo.find_by_user_id(user_id)
            assert len(results) >= 1

            logger.info("✅ Query succeeded despite KV-Storage failure")

        finally:
            # Restore original KV-Storage
            repo._kv_storage = original_kv

        # Clean up
        await repo.delete_by_user_id(user_id)
        logger.info("✅ Test graceful degradation passed")

    except Exception as e:
        logger.error("❌ Test failed: %s", e)
        raise


async def test_delete_by_user_id_with_kv_batch_delete():
    """
    Test delete_by_user_id performs batch delete in KV-Storage

    Validates:
    - All user records are deleted from MongoDB
    - Batch delete is called for KV-Storage
    - Event IDs are correctly collected for batch delete
    """
    logger.info("Starting test: delete_by_user_id with KV batch delete...")

    repo = get_bean_by_type(MemCellRawRepository)
    user_id = "test_kv_batch_delete_001"

    try:
        # Clean up
        await repo.delete_by_user_id(user_id)

        # Create test data
        for i in range(5):
            memcell = await create_test_memcell(user_id, f"Test batch delete {i+1}")
            await repo.append_memcell(memcell)

        # Mock KV-Storage
        mock_kv = create_mock_kv_storage()
        mock_kv.batch_delete = AsyncMock(return_value=5)

        original_kv = repo._kv_storage
        repo._kv_storage = mock_kv

        try:
            # Execute batch delete
            deleted_count = await repo.delete_by_user_id(user_id)
            assert deleted_count == 5

            # Verify KV-Storage batch_delete was called
            mock_kv.batch_delete.assert_called_once()
            call_args = mock_kv.batch_delete.call_args
            assert len(call_args.kwargs["keys"]) == 5

            logger.info("✅ Verified batch delete from MongoDB and KV-Storage")

        finally:
            # Restore original KV-Storage
            repo._kv_storage = original_kv

        logger.info("✅ Test delete_by_user_id with KV batch delete passed")

    except Exception as e:
        logger.error("❌ Test failed: %s", e)
        raise


async def test_delete_by_time_range_with_kv_batch_delete():
    """
    Test delete_by_time_range performs batch delete in KV-Storage

    Validates:
    - Records in time range are deleted from MongoDB
    - Batch delete is called for KV-Storage with correct event IDs
    """
    logger.info("Starting test: delete_by_time_range with KV batch delete...")

    repo = get_bean_by_type(MemCellRawRepository)
    user_id = "test_kv_time_delete_001"

    try:
        # Clean up
        await repo.delete_by_user_id(user_id)

        # Create test data with time spread
        now = get_now_with_timezone()
        for i in range(5):
            memcell = MemCell(
                user_id=user_id,
                timestamp=now - timedelta(days=i),
                summary=f"Test time delete {i+1}",
                type=DataTypeEnum.CONVERSATION,
            )
            await repo.append_memcell(memcell)

        # Mock KV-Storage
        mock_kv = create_mock_kv_storage()
        mock_kv.batch_delete = AsyncMock(return_value=3)

        original_kv = repo._kv_storage
        repo._kv_storage = mock_kv

        try:
            # Delete records from last 3 days
            start_time = now - timedelta(days=3)
            end_time = now + timedelta(days=1)

            deleted_count = await repo.delete_by_time_range(
                start_time, end_time, user_id=user_id
            )
            # Should delete at least 3 records (the ones we just created in range)
            assert deleted_count >= 3

            # Verify KV-Storage batch_delete was called
            mock_kv.batch_delete.assert_called_once()
            call_args = mock_kv.batch_delete.call_args
            # Should have at least 3 keys
            assert len(call_args.kwargs["keys"]) >= 3

            logger.info("✅ Verified time range batch delete with KV-Storage")

        finally:
            # Restore original KV-Storage
            repo._kv_storage = original_kv

        # Clean up
        await repo.delete_by_user_id(user_id)
        logger.info("✅ Test delete_by_time_range with KV batch delete passed")

    except Exception as e:
        logger.error("❌ Test failed: %s", e)
        raise


async def test_various_query_methods_with_kv_validation():
    """
    Test various query methods all perform KV validation

    Tests:
    - find_by_user_and_time_range
    - find_by_group_id
    - find_by_time_range
    - find_by_participants
    - search_by_keywords
    - get_latest_by_user

    Validates that all query methods call batch validation
    """
    logger.info("Starting test: various query methods with KV validation...")

    repo = get_bean_by_type(MemCellRawRepository)
    user_id = "test_kv_queries_001"
    group_id = "test_group_001"

    try:
        # Clean up
        await repo.delete_by_user_id(user_id)

        # Create test data
        now = get_now_with_timezone()
        for i in range(3):
            memcell = MemCell(
                user_id=user_id,
                group_id=group_id,
                timestamp=now - timedelta(hours=i),
                summary=f"Test query {i+1}",
                type=DataTypeEnum.CONVERSATION,
                keywords=["test", f"keyword{i+1}"],
                participants=["User A", "User B"],
            )
            await repo.append_memcell(memcell)

        # Mock KV-Storage
        mock_kv = create_mock_kv_storage()
        mock_kv.batch_get = AsyncMock(return_value={})

        original_kv = repo._kv_storage
        repo._kv_storage = mock_kv

        try:
            # Test find_by_user_and_time_range
            start_time = now - timedelta(days=1)
            end_time = now + timedelta(days=1)
            results = await repo.find_by_user_and_time_range(user_id, start_time, end_time)
            assert len(results) == 3
            assert mock_kv.batch_get.call_count == 1
            logger.info("✅ find_by_user_and_time_range calls KV validation")

            # Reset mock
            mock_kv.batch_get.reset_mock()

            # Test find_by_group_id
            results = await repo.find_by_group_id(group_id)
            assert len(results) == 3
            assert mock_kv.batch_get.call_count == 1
            logger.info("✅ find_by_group_id calls KV validation")

            # Reset mock
            mock_kv.batch_get.reset_mock()

            # Test find_by_time_range
            results = await repo.find_by_time_range(start_time, end_time)
            assert len(results) >= 3
            assert mock_kv.batch_get.call_count == 1
            logger.info("✅ find_by_time_range calls KV validation")

            # Reset mock
            mock_kv.batch_get.reset_mock()

            # Test find_by_participants
            results = await repo.find_by_participants(["User A"])
            assert len(results) >= 3
            assert mock_kv.batch_get.call_count == 1
            logger.info("✅ find_by_participants calls KV validation")

            # Reset mock
            mock_kv.batch_get.reset_mock()

            # Test search_by_keywords
            results = await repo.search_by_keywords(["test"])
            assert len(results) >= 3
            assert mock_kv.batch_get.call_count == 1
            logger.info("✅ search_by_keywords calls KV validation")

            # Reset mock
            mock_kv.batch_get.reset_mock()

            # Test get_latest_by_user
            results = await repo.get_latest_by_user(user_id, limit=2)
            assert len(results) == 2
            assert mock_kv.batch_get.call_count == 1
            logger.info("✅ get_latest_by_user calls KV validation")

        finally:
            # Restore original KV-Storage
            repo._kv_storage = original_kv

        # Clean up
        await repo.delete_by_user_id(user_id)
        logger.info("✅ Test various query methods with KV validation passed")

    except Exception as e:
        logger.error("❌ Test failed: %s", e)
        raise


# ==================== Test Runner ====================


async def run_all_kv_integration_tests():
    """Run all KV integration tests"""
    logger.info("🚀 Starting KV-Storage integration tests for MemCellRawRepository...")

    try:
        # Write operation tests
        await test_append_memcell_with_kv_dual_write()
        await test_update_memcell_with_kv_dual_write()
        await test_delete_memcell_with_kv_dual_delete()

        # Read operation tests
        await test_get_by_event_id_with_kv_validation()
        await test_get_by_event_ids_with_kv_batch_validation()
        await test_find_by_user_id_with_kv_validation()

        # Batch delete tests
        await test_delete_by_user_id_with_kv_batch_delete()
        await test_delete_by_time_range_with_kv_batch_delete()

        # Degradation test
        await test_graceful_degradation_when_kv_unavailable()

        # Various query methods test
        await test_various_query_methods_with_kv_validation()

        logger.info("✅✅✅ All KV-Storage integration tests completed!")

    except Exception as e:
        logger.error("❌ Error occurred during KV integration testing: %s", e)
        raise


if __name__ == "__main__":
    asyncio.run(run_all_kv_integration_tests())
