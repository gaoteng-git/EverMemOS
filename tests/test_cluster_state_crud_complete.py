#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete CRUD Test for ClusterStateRawRepository with KV-Storage

This test file comprehensively tests all CRUD methods in ClusterStateRawRepository
with the dual MongoDB + KV-Storage pattern. Each test follows the pattern:
1. Create test data (upsert)
2. Read/Query test data
3. Verify data consistency between MongoDB and KV-Storage
4. Verify data integrity (inserted == retrieved)

Modified methods tested:
- save_cluster_state
- load_cluster_state
- get_by_group_id
- upsert_by_group_id
- get_cluster_assignments
- delete_by_group_id
- delete_all
"""

import asyncio
import pytest
import pytest_asyncio
import uuid
from typing import Dict, Any, List, TYPE_CHECKING

# Mark all test functions in this module as asyncio tests
pytestmark = pytest.mark.asyncio

# Delay imports to avoid loading beanie at module level
if TYPE_CHECKING:
    from infra_layer.adapters.out.persistence.document.memory.cluster_state import (
        ClusterState,
    )
    from infra_layer.adapters.out.persistence.repository.cluster_state_raw_repository import (
        ClusterStateRawRepository,
    )
    from infra_layer.adapters.out.persistence.kv_storage import KVStorageInterface


# ==================== Test Fixtures ====================


@pytest_asyncio.fixture
async def repository():
    """Get ClusterStateRawRepository instance"""
    from core.di import get_bean_by_type
    from infra_layer.adapters.out.persistence.repository.cluster_state_raw_repository import (
        ClusterStateRawRepository,
    )
    repo = get_bean_by_type(ClusterStateRawRepository)
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
def test_group_id():
    """Generate unique test group ID"""
    return f"test_group_{uuid.uuid4().hex[:8]}"


# ==================== Test Helpers ====================


def create_test_cluster_state_dict(
    group_id: str,
    num_events: int = 3,
) -> Dict[str, Any]:
    """Helper function to create a test ClusterState dictionary"""
    event_ids = [f"event_{uuid.uuid4().hex[:8]}" for _ in range(num_events)]
    timestamps = [1234567890.0 + i * 100 for i in range(num_events)]

    # Assign events to clusters
    cluster_assignments = {}
    cluster_counts = {}
    for i, event_id in enumerate(event_ids):
        cluster_id = f"cluster_{chr(97 + (i % 2))}"  # cluster_a or cluster_b
        cluster_assignments[event_id] = cluster_id
        cluster_counts[cluster_id] = cluster_counts.get(cluster_id, 0) + 1

    cluster_ids = list(set(cluster_assignments.values()))

    # Create cluster centroids
    cluster_centroids = {
        cluster_id: [0.1 * ord(cluster_id[-1]), 0.2, 0.3]
        for cluster_id in cluster_ids
    }

    cluster_last_ts = {
        cluster_id: max(
            timestamps[i]
            for i, eid in enumerate(event_ids)
            if cluster_assignments[eid] == cluster_id
        )
        for cluster_id in cluster_ids
    }

    return {
        "group_id": group_id,
        "event_ids": event_ids,
        "timestamps": timestamps,
        "cluster_ids": cluster_ids,
        "eventid_to_cluster": cluster_assignments,
        "next_cluster_idx": len(cluster_ids),
        "cluster_centroids": cluster_centroids,
        "cluster_counts": cluster_counts,
        "cluster_last_ts": cluster_last_ts,
    }


def assert_cluster_state_equal(cs1, cs2, check_id: bool = True):
    """Assert two ClusterState objects are equal (comparing all fields)"""
    if check_id:
        assert str(cs1.id) == str(cs2.id), "IDs don't match"

    assert cs1.group_id == cs2.group_id, "group_id doesn't match"
    assert cs1.event_ids == cs2.event_ids, "event_ids don't match"
    assert cs1.timestamps == cs2.timestamps, "timestamps don't match"
    assert cs1.cluster_ids == cs2.cluster_ids, "cluster_ids don't match"
    assert cs1.eventid_to_cluster == cs2.eventid_to_cluster, "eventid_to_cluster doesn't match"
    assert cs1.next_cluster_idx == cs2.next_cluster_idx, "next_cluster_idx doesn't match"
    assert cs1.cluster_centroids == cs2.cluster_centroids, "cluster_centroids don't match"
    assert cs1.cluster_counts == cs2.cluster_counts, "cluster_counts don't match"
    assert cs1.cluster_last_ts == cs2.cluster_last_ts, "cluster_last_ts doesn't match"


# ==================== Test Classes ====================


class TestBasicCRUD:
    """Test basic CRUD operations"""

    @pytest.mark.asyncio
    async def test_save_and_load_cluster_state(
        self, repository, kv_storage, test_group_id
    ):
        """Test save_cluster_state and load_cluster_state (ClusterStorage interface)"""
        from infra_layer.adapters.out.persistence.document.memory.cluster_state import (
            ClusterState,
        )

        # 1. Create test state dict
        state_dict = create_test_cluster_state_dict(test_group_id, num_events=3)

        # 2. Save using save_cluster_state
        success = await repository.save_cluster_state(test_group_id, state_dict)
        assert success, "save_cluster_state should return True"

        # 3. Load using load_cluster_state
        loaded_dict = await repository.load_cluster_state(test_group_id)
        assert loaded_dict is not None, "load_cluster_state should return state dict"

        # 4. Verify core fields match
        assert loaded_dict["group_id"] == test_group_id
        assert loaded_dict["event_ids"] == state_dict["event_ids"]
        assert loaded_dict["eventid_to_cluster"] == state_dict["eventid_to_cluster"]
        assert loaded_dict["cluster_counts"] == state_dict["cluster_counts"]

        # 5. Verify MongoDB Lite exists (only group_id)
        from infra_layer.adapters.out.persistence.document.memory.cluster_state_lite import (
            ClusterStateLite,
        )
        lite = await ClusterStateLite.find_one({"group_id": test_group_id})
        assert lite is not None, "ClusterStateLite should exist in MongoDB"
        assert lite.group_id == test_group_id

        # 6. Verify KV-Storage has complete data
        cluster_state_id = str(lite.id)
        kv_json = await kv_storage.get(cluster_state_id)
        assert kv_json is not None, "KV-Storage should contain full ClusterState"

        full_state = ClusterState.model_validate_json(kv_json)
        assert full_state.group_id == test_group_id
        assert full_state.event_ids == state_dict["event_ids"]

        # Cleanup
        await repository.delete_by_group_id(test_group_id)

    @pytest.mark.asyncio
    async def test_upsert_new_cluster_state(
        self, repository, kv_storage, test_group_id
    ):
        """Test upsert_by_group_id for new cluster state"""
        from infra_layer.adapters.out.persistence.document.memory.cluster_state import (
            ClusterState,
        )

        # 1. Create test state dict
        state_dict = create_test_cluster_state_dict(test_group_id, num_events=5)

        # 2. Upsert (insert)
        result = await repository.upsert_by_group_id(test_group_id, state_dict)
        assert result is not None, "upsert_by_group_id should return ClusterState"
        assert result.group_id == test_group_id
        assert result.id is not None, "ClusterState should have ID"

        # 3. Verify MongoDB Lite
        from infra_layer.adapters.out.persistence.document.memory.cluster_state_lite import (
            ClusterStateLite,
        )
        lite = await ClusterStateLite.find_one({"group_id": test_group_id})
        assert lite is not None
        assert lite.group_id == test_group_id

        # 4. Verify KV-Storage
        kv_json = await kv_storage.get(str(result.id))
        assert kv_json is not None, "KV-Storage should contain full ClusterState"

        # Cleanup
        await repository.delete_by_group_id(test_group_id)

    @pytest.mark.asyncio
    async def test_upsert_update_cluster_state(
        self, repository, kv_storage, test_group_id
    ):
        """Test upsert_by_group_id for updating existing cluster state"""
        # 1. Create and insert initial state
        state_dict_v1 = create_test_cluster_state_dict(test_group_id, num_events=3)
        result_v1 = await repository.upsert_by_group_id(test_group_id, state_dict_v1)
        assert result_v1 is not None
        original_id = result_v1.id

        # 2. Update with new data
        state_dict_v2 = create_test_cluster_state_dict(test_group_id, num_events=5)
        result_v2 = await repository.upsert_by_group_id(test_group_id, state_dict_v2)

        # 3. Verify ID remains the same (update, not insert)
        assert result_v2 is not None
        assert result_v2.id == original_id, "ID should remain the same on update"

        # 4. Verify new data is stored
        assert len(result_v2.event_ids) == 5, "Should have 5 events after update"

        # 5. Verify KV-Storage has updated data
        kv_json = await kv_storage.get(str(result_v2.id))
        assert kv_json is not None
        from infra_layer.adapters.out.persistence.document.memory.cluster_state import (
            ClusterState,
        )
        full_state = ClusterState.model_validate_json(kv_json)
        assert len(full_state.event_ids) == 5

        # Cleanup
        await repository.delete_by_group_id(test_group_id)

    @pytest.mark.asyncio
    async def test_get_by_group_id(self, repository, kv_storage, test_group_id):
        """Test get_by_group_id method"""
        # 1. Create and save state
        state_dict = create_test_cluster_state_dict(test_group_id, num_events=4)
        saved = await repository.upsert_by_group_id(test_group_id, state_dict)
        assert saved is not None

        # 2. Get by group_id
        retrieved = await repository.get_by_group_id(test_group_id)
        assert retrieved is not None, "get_by_group_id should return ClusterState"

        # 3. Verify all fields match
        assert_cluster_state_equal(saved, retrieved)

        # 4. Test non-existent group_id
        non_existent = await repository.get_by_group_id("non_existent_group")
        assert non_existent is None, "Should return None for non-existent group_id"

        # Cleanup
        await repository.delete_by_group_id(test_group_id)


class TestClusterAssignments:
    """Test cluster assignment operations"""

    @pytest.mark.asyncio
    async def test_get_cluster_assignments(self, repository, test_group_id):
        """Test get_cluster_assignments method"""
        # 1. Create state with specific assignments
        state_dict = create_test_cluster_state_dict(test_group_id, num_events=6)
        await repository.upsert_by_group_id(test_group_id, state_dict)

        # 2. Get cluster assignments
        assignments = await repository.get_cluster_assignments(test_group_id)

        # 3. Verify assignments match
        assert assignments is not None
        assert assignments == state_dict["eventid_to_cluster"]

        # 4. Verify all events have assignments
        assert len(assignments) == len(state_dict["event_ids"])

        # 5. Test non-existent group
        empty_assignments = await repository.get_cluster_assignments("non_existent")
        assert empty_assignments == {}, "Should return empty dict for non-existent group"

        # Cleanup
        await repository.delete_by_group_id(test_group_id)


class TestDeletion:
    """Test deletion operations"""

    @pytest.mark.asyncio
    async def test_delete_by_group_id(self, repository, kv_storage, test_group_id):
        """Test delete_by_group_id method"""
        # 1. Create and save state
        state_dict = create_test_cluster_state_dict(test_group_id, num_events=3)
        saved = await repository.upsert_by_group_id(test_group_id, state_dict)
        cluster_state_id = str(saved.id)

        # 2. Verify exists in both storages
        from infra_layer.adapters.out.persistence.document.memory.cluster_state_lite import (
            ClusterStateLite,
        )
        lite_before = await ClusterStateLite.find_one({"group_id": test_group_id})
        assert lite_before is not None, "Should exist in MongoDB before deletion"

        kv_before = await kv_storage.get(cluster_state_id)
        assert kv_before is not None, "Should exist in KV-Storage before deletion"

        # 3. Delete
        success = await repository.delete_by_group_id(test_group_id)
        assert success, "delete_by_group_id should return True"

        # 4. Verify deleted from MongoDB
        lite_after = await ClusterStateLite.find_one({"group_id": test_group_id})
        assert lite_after is None, "Should be deleted from MongoDB"

        # 5. Verify deleted from KV-Storage
        kv_after = await kv_storage.get(cluster_state_id)
        assert kv_after is None, "Should be deleted from KV-Storage"

    @pytest.mark.asyncio
    async def test_delete_all(self, repository, kv_storage):
        """Test delete_all method"""
        # 1. Create multiple cluster states
        group_ids = [f"test_group_{uuid.uuid4().hex[:8]}" for _ in range(3)]
        cluster_state_ids = []

        for group_id in group_ids:
            state_dict = create_test_cluster_state_dict(group_id, num_events=2)
            saved = await repository.upsert_by_group_id(group_id, state_dict)
            cluster_state_ids.append(str(saved.id))

        # 2. Verify all exist
        from infra_layer.adapters.out.persistence.document.memory.cluster_state_lite import (
            ClusterStateLite,
        )
        lites_before = await ClusterStateLite.find_all().to_list()
        assert len(lites_before) >= 3, "Should have at least 3 ClusterStates"

        # 3. Delete all
        count = await repository.delete_all()
        assert count >= 3, f"Should delete at least 3 records, got {count}"

        # 4. Verify all deleted from MongoDB
        lites_after = await ClusterStateLite.find_all().to_list()
        assert len(lites_after) == 0, "Should delete all from MongoDB"

        # 5. Verify all deleted from KV-Storage
        for cluster_state_id in cluster_state_ids:
            kv_after = await kv_storage.get(cluster_state_id)
            assert kv_after is None, f"Should delete {cluster_state_id} from KV-Storage"


class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_load_nonexistent_cluster_state(self, repository):
        """Test loading non-existent cluster state"""
        result = await repository.load_cluster_state("nonexistent_group_123")
        assert result is None, "Should return None for non-existent group"

    @pytest.mark.asyncio
    async def test_empty_cluster_state(self, repository, test_group_id):
        """Test cluster state with minimal data"""
        # Create minimal state dict
        minimal_state = {
            "group_id": test_group_id,
            "event_ids": [],
            "timestamps": [],
            "cluster_ids": [],
            "eventid_to_cluster": {},
            "next_cluster_idx": 0,
            "cluster_centroids": {},
            "cluster_counts": {},
            "cluster_last_ts": {},
        }

        # Save and load
        success = await repository.save_cluster_state(test_group_id, minimal_state)
        assert success, "Should save empty cluster state"

        loaded = await repository.load_cluster_state(test_group_id)
        assert loaded is not None
        assert loaded["event_ids"] == []
        assert loaded["eventid_to_cluster"] == {}

        # Cleanup
        await repository.delete_by_group_id(test_group_id)

    @pytest.mark.asyncio
    async def test_large_cluster_state(self, repository, test_group_id):
        """Test cluster state with large number of events"""
        # Create state with 100 events
        state_dict = create_test_cluster_state_dict(test_group_id, num_events=100)

        # Save
        result = await repository.upsert_by_group_id(test_group_id, state_dict)
        assert result is not None
        assert len(result.event_ids) == 100

        # Load and verify
        loaded = await repository.load_cluster_state(test_group_id)
        assert loaded is not None
        assert len(loaded["event_ids"]) == 100

        # Cleanup
        await repository.delete_by_group_id(test_group_id)
