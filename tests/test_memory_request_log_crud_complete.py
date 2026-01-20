#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete CRUD Test for MemoryRequestLogRepository with KV-Storage

This test file comprehensively tests all CRUD methods in MemoryRequestLogRepository
with the dual MongoDB + KV-Storage pattern. Each test follows the pattern:
1. Create test data (save)
2. Read/Query test data
3. Verify data consistency between MongoDB and KV-Storage
4. Verify data integrity (saved == retrieved)

Methods tested (10 total):
- save
- get_by_request_id
- find_by_group_id
- find_by_group_id_with_statuses
- find_by_user_id
- delete_by_group_id
- confirm_accumulation_by_group_id
- confirm_accumulation_by_message_ids
- mark_as_used_by_group_id
- find_pending_by_filters
"""

import asyncio
import pytest
import pytest_asyncio
import uuid
from datetime import timedelta
from typing import List, TYPE_CHECKING

# Mark all test functions in this module as asyncio tests
pytestmark = pytest.mark.asyncio

# Delay imports to avoid loading beanie at module level
if TYPE_CHECKING:
    from infra_layer.adapters.out.persistence.document.request.memory_request_log import (
        MemoryRequestLog,
    )
    from infra_layer.adapters.out.persistence.repository.memory_request_log_repository import (
        MemoryRequestLogRepository,
    )
    from infra_layer.adapters.out.persistence.kv_storage import KVStorageInterface


# ==================== Test Fixtures ====================


@pytest_asyncio.fixture
async def repository():
    """Get MemoryRequestLogRepository instance"""
    from core.di import get_bean_by_type
    from infra_layer.adapters.out.persistence.repository.memory_request_log_repository import (
        MemoryRequestLogRepository,
    )

    repo = get_bean_by_type(MemoryRequestLogRepository)
    yield repo
    # Cleanup is handled by individual tests


@pytest_asyncio.fixture
async def kv_storage():
    """Get KV-Storage instance"""
    from core.di import get_bean_by_type
    from infra_layer.adapters.out.persistence.kv_storage import KVStorageInterface

    kv = get_bean_by_type(KVStorageInterface)
    yield kv


@pytest.fixture
def test_user_id():
    """Generate unique test user ID"""
    return f"test_user_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def test_group_id():
    """Generate unique test group ID"""
    return f"test_group_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def test_request_id():
    """Generate unique test request ID"""
    return f"test_request_{uuid.uuid4().hex[:8]}"


# ==================== Test Helpers ====================


def create_test_memory_request_log(
    group_id: str,
    request_id: str,
    user_id: str = None,
    message_id: str = None,
    sender: str = None,
    content: str = "Test message content",
    sync_status: int = -1,
):
    """Helper function to create a test MemoryRequestLog with all fields"""
    from infra_layer.adapters.out.persistence.document.request.memory_request_log import (
        MemoryRequestLog,
    )

    message_id = message_id or f"msg_{uuid.uuid4().hex[:8]}"
    sender = sender or user_id or f"sender_{uuid.uuid4().hex[:8]}"

    return MemoryRequestLog(
        # Core fields
        group_id=group_id,
        request_id=request_id,
        user_id=user_id or sender,
        # Message core fields
        message_id=message_id,
        message_create_time="2025-01-20T10:00:00+08:00",
        sender=sender,
        sender_name=f"Sender_{sender[-8:]}",
        role="user",
        content=content,
        group_name=f"TestGroup_{group_id[-8:]}",
        refer_list=[f"ref_{uuid.uuid4().hex[:8]}"],
        # Raw input
        raw_input={
            "message_id": message_id,
            "content": content,
            "sender": sender,
        },
        raw_input_str=f'{{"message_id": "{message_id}", "content": "{content}"}}',
        # Request metadata
        version="1.0.0",
        endpoint_name="memorize",
        method="POST",
        url="/api/v1/memories",
        # Event association
        event_id=request_id,
        # Sync status
        sync_status=sync_status,
    )


def assert_memory_request_log_equal(log1, log2, check_id: bool = True):
    """Assert two MemoryRequestLog objects are equal"""
    if check_id:
        assert str(log1.id) == str(log2.id), "IDs don't match"

    # Core fields
    assert log1.group_id == log2.group_id, "group_id doesn't match"
    assert log1.request_id == log2.request_id, "request_id doesn't match"
    assert log1.user_id == log2.user_id, "user_id doesn't match"

    # Message fields
    assert log1.message_id == log2.message_id, "message_id doesn't match"
    assert log1.sender == log2.sender, "sender doesn't match"
    assert log1.content == log2.content, "content doesn't match"
    assert log1.sync_status == log2.sync_status, "sync_status doesn't match"


async def verify_kv_storage(repository, log_id: str) -> bool:
    """Verify data exists in KV-Storage"""
    from core.observation.logger import get_logger

    logger = get_logger(__name__)

    kv_storage = repository._dual_storage.get_kv_storage()
    if not kv_storage:
        logger.warning("KV-Storage not available")
        return False

    kv_json = await kv_storage.get(key=log_id)
    return kv_json is not None


# ==================== Test Cases ====================


def get_logger():
    """Helper to get logger instance"""
    from core.observation.logger import get_logger as _get_logger

    return _get_logger(__name__)


class TestBasicCRUD:
    """Test basic CRUD operations: Create, Read, Delete"""

    async def test_01_save_and_get_by_request_id(
        self, repository, test_group_id, test_request_id, test_user_id
    ):
        """
        Test: save + get_by_request_id
        Flow: Create a MemoryRequestLog -> Read it back -> Verify data matches
        """
        logger = get_logger()
        logger.info("=" * 60)
        logger.info("TEST: save + get_by_request_id")

        # 1. Create test MemoryRequestLog
        original = create_test_memory_request_log(
            group_id=test_group_id,
            request_id=test_request_id,
            user_id=test_user_id,
            content="Test log for get_by_request_id",
        )

        # 2. Save to repository
        created = await repository.save(original)
        assert created is not None, "Failed to save MemoryRequestLog"
        assert created.id is not None, "Created MemoryRequestLog should have ID"

        log_id = str(created.id)
        logger.info(f"✅ Created MemoryRequestLog with ID: {log_id}")

        # 3. Verify KV-Storage
        kv_exists = await verify_kv_storage(repository, log_id)
        logger.info(f"KV-Storage: {'✅ Exists' if kv_exists else '⚠️  Not found'}")

        # 4. Read back using get_by_request_id
        retrieved = await repository.get_by_request_id(test_request_id)
        assert retrieved is not None, "Failed to retrieve MemoryRequestLog"
        logger.info(f"✅ Retrieved MemoryRequestLog by request_id")

        # 5. Verify data matches
        assert_memory_request_log_equal(created, retrieved, check_id=True)
        logger.info(f"✅ Data integrity verified")

        # Cleanup
        await repository.delete_by_group_id(test_group_id)

    async def test_02_save_and_find_by_group_id(
        self, repository, test_group_id, test_user_id
    ):
        """
        Test: save + find_by_group_id
        Flow: Create 3 MemoryRequestLogs -> Query by group_id -> Verify results
        """
        logger = get_logger()
        logger.info("=" * 60)
        logger.info("TEST: save + find_by_group_id")

        # 1. Create 3 test MemoryRequestLogs
        created_list = []
        for i in range(3):
            request_id = f"req_{test_group_id}_{i}"
            original = create_test_memory_request_log(
                group_id=test_group_id,
                request_id=request_id,
                user_id=test_user_id,
                content=f"Test log {i+1} for group query",
            )
            created = await repository.save(original)
            assert created is not None
            created_list.append(created)
            logger.info(f"✅ Created MemoryRequestLog {i+1}: {created.id}")

        # 2. Query by group_id (sync_status=None to get all statuses)
        results = await repository.find_by_group_id(test_group_id, sync_status=None)
        assert len(results) == 3, f"Expected 3 results, got {len(results)}"
        logger.info(f"✅ Found {len(results)} MemoryRequestLogs for group")

        # 3. Verify all created logs are in results
        result_ids = {str(log.id) for log in results}
        for created in created_list:
            assert (
                str(created.id) in result_ids
            ), f"Created log {created.id} not in results"

        logger.info(f"✅ All created logs found in query results")

        # Cleanup
        await repository.delete_by_group_id(test_group_id)

    async def test_03_delete_by_group_id(
        self, repository, test_group_id, test_request_id, test_user_id
    ):
        """
        Test: save + delete_by_group_id + find_by_group_id
        Flow: Create -> Delete -> Verify deletion (MongoDB + KV)
        """
        logger = get_logger()
        logger.info("=" * 60)
        logger.info("TEST: delete_by_group_id")

        # 1. Create test MemoryRequestLog
        original = create_test_memory_request_log(
            group_id=test_group_id,
            request_id=test_request_id,
            user_id=test_user_id,
            content="Test log to be deleted",
        )
        created = await repository.save(original)
        assert created is not None
        log_id = str(created.id)
        logger.info(f"✅ Created MemoryRequestLog: {log_id}")

        # 2. Verify it exists (sync_status=None to get all statuses)
        results_before = await repository.find_by_group_id(test_group_id, sync_status=None)
        assert len(results_before) == 1, "Should have 1 log before deletion"

        # 3. Delete by group_id
        deleted_count = await repository.delete_by_group_id(test_group_id)
        assert deleted_count == 1, f"Expected to delete 1, got {deleted_count}"
        logger.info(f"✅ Deleted {deleted_count} MemoryRequestLog(s)")

        # 4. Verify deletion (sync_status=None to get all statuses)
        results_after = await repository.find_by_group_id(test_group_id, sync_status=None)
        assert len(results_after) == 0, "Should have 0 logs after deletion"
        logger.info(f"✅ Verified deletion: count = 0")

        # 5. Verify KV-Storage cleanup
        kv_exists = await verify_kv_storage(repository, log_id)
        assert not kv_exists, "KV-Storage should be cleaned up"
        logger.info(f"✅ KV-Storage cleaned up")


class TestQueryMethods:
    """Test query methods: find by various filters"""

    async def test_04_find_by_user_id(self, repository, test_user_id):
        """
        Test: save + find_by_user_id
        Flow: Create 3 logs for user -> Query by user_id -> Verify results
        """
        logger = get_logger()
        logger.info("=" * 60)
        logger.info("TEST: find_by_user_id")

        # Use unique group IDs to avoid interference
        test_groups = [f"group_{test_user_id}_{i}" for i in range(3)]

        # 1. Create 3 MemoryRequestLogs for the same user
        created_list = []
        for i, group_id in enumerate(test_groups):
            original = create_test_memory_request_log(
                group_id=group_id,
                request_id=f"req_{group_id}",
                user_id=test_user_id,
                content=f"Log {i+1} for user query",
            )
            created = await repository.save(original)
            created_list.append(created)

        logger.info(f"✅ Created {len(created_list)} logs for user: {test_user_id}")

        # 2. Query by user_id
        results = await repository.find_by_user_id(test_user_id)
        assert len(results) >= 3, f"Expected at least 3 results, got {len(results)}"
        logger.info(f"✅ Found {len(results)} logs for user")

        # 3. Verify all created logs are in results
        result_ids = {str(log.id) for log in results}
        for created in created_list:
            assert str(created.id) in result_ids, f"Log {created.id} not in results"

        logger.info(f"✅ All created logs found in query results")

        # Cleanup
        for group_id in test_groups:
            await repository.delete_by_group_id(group_id)

    async def test_05_find_by_group_id_with_statuses(
        self, repository, test_group_id, test_user_id
    ):
        """
        Test: save + find_by_group_id_with_statuses
        Flow: Create logs with different statuses -> Query by status -> Verify
        """
        logger = get_logger()
        logger.info("=" * 60)
        logger.info("TEST: find_by_group_id_with_statuses")

        # 1. Create logs with different sync_status values
        created_pending = []  # sync_status = -1
        created_accumulating = []  # sync_status = 0
        created_used = []  # sync_status = 1

        for i in range(2):
            # Pending (-1)
            log_pending = create_test_memory_request_log(
                group_id=test_group_id,
                request_id=f"req_pending_{i}",
                user_id=test_user_id,
                sync_status=-1,
            )
            created = await repository.save(log_pending)
            created_pending.append(created)

            # Accumulating (0)
            log_accumulating = create_test_memory_request_log(
                group_id=test_group_id,
                request_id=f"req_accumulating_{i}",
                user_id=test_user_id,
                sync_status=0,
            )
            created = await repository.save(log_accumulating)
            created_accumulating.append(created)

            # Used (1)
            log_used = create_test_memory_request_log(
                group_id=test_group_id,
                request_id=f"req_used_{i}",
                user_id=test_user_id,
                sync_status=1,
            )
            created = await repository.save(log_used)
            created_used.append(created)

        logger.info(
            f"✅ Created 6 logs: 2 pending, 2 accumulating, 2 used"
        )

        # 2. Query only pending (-1)
        results_pending = await repository.find_by_group_id_with_statuses(
            test_group_id, sync_status_list=[-1]
        )
        assert (
            len(results_pending) == 2
        ), f"Expected 2 pending logs, got {len(results_pending)}"
        logger.info(f"✅ Found {len(results_pending)} pending logs")

        # 3. Query pending + accumulating (-1, 0)
        results_both = await repository.find_by_group_id_with_statuses(
            test_group_id, sync_status_list=[-1, 0]
        )
        assert (
            len(results_both) == 4
        ), f"Expected 4 logs (pending+accumulating), got {len(results_both)}"
        logger.info(f"✅ Found {len(results_both)} pending+accumulating logs")

        # 4. Verify statuses
        for log in results_both:
            assert log.sync_status in [
                -1,
                0,
            ], f"Unexpected sync_status: {log.sync_status}"

        logger.info(f"✅ Status filtering verified")

        # Cleanup
        await repository.delete_by_group_id(test_group_id)

    async def test_06_find_pending_by_filters(self, repository, test_user_id):
        """
        Test: save + find_pending_by_filters
        Flow: Create logs with different filters -> Query -> Verify
        """
        logger = get_logger()
        logger.info("=" * 60)
        logger.info("TEST: find_pending_by_filters")

        # Use unique group IDs
        group1 = f"group1_{test_user_id}"
        group2 = f"group2_{test_user_id}"

        # 1. Create logs for different groups
        for group_id in [group1, group2]:
            for i in range(2):
                log = create_test_memory_request_log(
                    group_id=group_id,
                    request_id=f"req_{group_id}_{i}",
                    user_id=test_user_id,
                    sync_status=-1,
                )
                await repository.save(log)

        logger.info(f"✅ Created 4 logs across 2 groups")

        # 2. Query by specific group_id
        results_group1 = await repository.find_pending_by_filters(
            group_id=group1, sync_status_list=[-1]
        )
        assert (
            len(results_group1) == 2
        ), f"Expected 2 logs for group1, got {len(results_group1)}"
        logger.info(f"✅ Found {len(results_group1)} logs for group1")

        # 3. Query by user_id (all groups)
        from core.oxm.constants import MAGIC_ALL

        results_user = await repository.find_pending_by_filters(
            user_id=test_user_id, group_id=MAGIC_ALL, sync_status_list=[-1]
        )
        assert (
            len(results_user) >= 4
        ), f"Expected at least 4 logs for user, got {len(results_user)}"
        logger.info(f"✅ Found {len(results_user)} logs for user")

        # Cleanup
        await repository.delete_by_group_id(group1)
        await repository.delete_by_group_id(group2)


class TestSyncStatusManagement:
    """Test sync status management: state transitions"""

    async def test_07_confirm_accumulation_by_group_id(
        self, repository, test_group_id, test_user_id
    ):
        """
        Test: confirm_accumulation_by_group_id
        Flow: Create pending logs (-1) -> Confirm -> Verify status changed to 0
        """
        logger = get_logger()
        logger.info("=" * 60)
        logger.info("TEST: confirm_accumulation_by_group_id")

        # 1. Create 3 pending logs (sync_status = -1)
        for i in range(3):
            log = create_test_memory_request_log(
                group_id=test_group_id,
                request_id=f"req_{i}",
                user_id=test_user_id,
                sync_status=-1,
            )
            await repository.save(log)

        logger.info(f"✅ Created 3 pending logs (sync_status=-1)")

        # 2. Verify initial status
        results_before = await repository.find_by_group_id_with_statuses(
            test_group_id, sync_status_list=[-1]
        )
        assert len(results_before) == 3, "Should have 3 pending logs"

        # 3. Confirm accumulation (-1 -> 0)
        modified_count = await repository.confirm_accumulation_by_group_id(
            test_group_id
        )
        assert modified_count == 3, f"Expected to modify 3, got {modified_count}"
        logger.info(f"✅ Confirmed accumulation: {modified_count} logs updated")

        # 4. Verify status changed to 0
        results_after = await repository.find_by_group_id_with_statuses(
            test_group_id, sync_status_list=[0]
        )
        assert (
            len(results_after) == 3
        ), f"Expected 3 accumulating logs, got {len(results_after)}"
        logger.info(f"✅ Status transition verified: -1 -> 0")

        # Cleanup
        await repository.delete_by_group_id(test_group_id)

    async def test_08_confirm_accumulation_by_message_ids(
        self, repository, test_group_id, test_user_id
    ):
        """
        Test: confirm_accumulation_by_message_ids
        Flow: Create 3 pending logs -> Confirm only 2 by message_id -> Verify
        """
        logger = get_logger()
        logger.info("=" * 60)
        logger.info("TEST: confirm_accumulation_by_message_ids")

        # 1. Create 3 pending logs
        message_ids = []
        for i in range(3):
            msg_id = f"msg_{test_group_id}_{i}"
            log = create_test_memory_request_log(
                group_id=test_group_id,
                request_id=f"req_{i}",
                user_id=test_user_id,
                message_id=msg_id,
                sync_status=-1,
            )
            await repository.save(log)
            message_ids.append(msg_id)

        logger.info(f"✅ Created 3 pending logs")

        # 2. Confirm only 2 messages
        target_message_ids = message_ids[:2]
        modified_count = await repository.confirm_accumulation_by_message_ids(
            test_group_id, target_message_ids
        )
        assert modified_count == 2, f"Expected to modify 2, got {modified_count}"
        logger.info(f"✅ Confirmed accumulation for 2 specific messages")

        # 3. Verify: 2 should be status=0, 1 should still be status=-1
        results_accumulating = await repository.find_by_group_id_with_statuses(
            test_group_id, sync_status_list=[0]
        )
        results_pending = await repository.find_by_group_id_with_statuses(
            test_group_id, sync_status_list=[-1]
        )

        assert (
            len(results_accumulating) == 2
        ), f"Expected 2 accumulating, got {len(results_accumulating)}"
        assert len(results_pending) == 1, f"Expected 1 pending, got {len(results_pending)}"
        logger.info(f"✅ Precise status update verified: 2 updated, 1 unchanged")

        # Cleanup
        await repository.delete_by_group_id(test_group_id)

    async def test_09_mark_as_used_by_group_id(
        self, repository, test_group_id, test_user_id
    ):
        """
        Test: mark_as_used_by_group_id
        Flow: Create pending and accumulating logs -> Mark as used -> Verify
        """
        logger = get_logger()
        logger.info("=" * 60)
        logger.info("TEST: mark_as_used_by_group_id")

        # 1. Create logs with different statuses
        for i in range(2):
            # Pending (-1)
            log_pending = create_test_memory_request_log(
                group_id=test_group_id,
                request_id=f"req_pending_{i}",
                user_id=test_user_id,
                sync_status=-1,
            )
            await repository.save(log_pending)

            # Accumulating (0)
            log_accumulating = create_test_memory_request_log(
                group_id=test_group_id,
                request_id=f"req_accumulating_{i}",
                user_id=test_user_id,
                sync_status=0,
            )
            await repository.save(log_accumulating)

        logger.info(f"✅ Created 4 logs: 2 pending, 2 accumulating")

        # 2. Mark all as used (both -1 and 0 -> 1)
        modified_count = await repository.mark_as_used_by_group_id(test_group_id)
        assert modified_count == 4, f"Expected to modify 4, got {modified_count}"
        logger.info(f"✅ Marked as used: {modified_count} logs updated")

        # 3. Verify all are now status=1
        results_used = await repository.find_by_group_id_with_statuses(
            test_group_id, sync_status_list=[1]
        )
        assert len(results_used) == 4, f"Expected 4 used logs, got {len(results_used)}"
        logger.info(f"✅ Status transition verified: all -> 1")

        # Cleanup
        await repository.delete_by_group_id(test_group_id)


class TestEdgeCases:
    """Test edge cases and error handling"""

    async def test_10_get_nonexistent_request_id(self, repository):
        """
        Test: get_by_request_id with non-existent ID
        Expected: Should return None
        """
        logger = get_logger()
        logger.info("=" * 60)
        logger.info("TEST: get_by_request_id (non-existent)")

        fake_id = "nonexistent_request_id"
        result = await repository.get_by_request_id(fake_id)

        assert result is None, "Non-existent ID should return None"
        logger.info(f"✅ Non-existent ID handled correctly: returned None")

    async def test_11_verify_audit_fields(
        self, repository, test_group_id, test_request_id, test_user_id
    ):
        """
        Test: Verify created_at and updated_at are set correctly
        """
        logger = get_logger()
        logger.info("=" * 60)
        logger.info("TEST: Verify created_at and updated_at fields")

        # 1. Create and save MemoryRequestLog
        original = create_test_memory_request_log(
            group_id=test_group_id,
            request_id=test_request_id,
            user_id=test_user_id,
        )
        created = await repository.save(original)
        assert created is not None, "save should return MemoryRequestLog"

        # 2. Verify audit fields are set after save
        assert created.created_at is not None, "❌ BUG: created_at should not be None!"
        assert created.updated_at is not None, "❌ BUG: updated_at should not be None!"
        logger.info(
            f"✅ After save: created_at={created.created_at}, updated_at={created.updated_at}"
        )

        # 3. Retrieve from KV-Storage and verify persistence
        retrieved = await repository.get_by_request_id(test_request_id)
        assert retrieved is not None, "get_by_request_id should return MemoryRequestLog"
        assert (
            retrieved.created_at is not None
        ), "❌ BUG: created_at should persist in KV-Storage!"
        assert (
            retrieved.updated_at is not None
        ), "❌ BUG: updated_at should persist in KV-Storage!"
        logger.info(
            f"✅ After retrieve: created_at={retrieved.created_at}, updated_at={retrieved.updated_at}"
        )

        # 4. Verify created_at equals updated_at for newly created records
        time_diff = abs((retrieved.created_at - retrieved.updated_at).total_seconds())
        assert (
            time_diff < 1
        ), "created_at and updated_at should be nearly identical for new records"
        logger.info(f"✅ created_at ≈ updated_at (diff: {time_diff:.6f}s)")

        # Cleanup
        await repository.delete_by_group_id(test_group_id)
        logger.info("✅ Audit fields verification passed")


# ==================== Main Test Runner ====================


if __name__ == "__main__":
    """
    Run all tests with pytest

    Usage:
        pytest tests/test_memory_request_log_crud_complete.py -v -s
    """
    pytest.main([__file__, "-v", "-s"])
