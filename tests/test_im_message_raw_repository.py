#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test the query functionality of ImMessageRawRepository

Test contents include:
1. Query operations based on ID
2. Query operations based on room ID (supporting message type and time range filtering)
3. Query operations based on task type
4. Validation of various query parameter combinations
"""

import asyncio
from datetime import datetime, timedelta

from core.di import get_bean_by_type
from common_utils.datetime_utils import get_now_with_timezone, to_iso_format
from infra_layer.adapters.out.persistence.repository.tanka.im_message_raw_repository import (
    ImMessageRawRepository,
)
from core.observation.logger import get_logger

logger = get_logger(__name__)


async def get_sample_data():
    """Retrieve some sample data from the database for testing"""
    logger.info("Retrieving sample data...")

    repo = get_bean_by_type(ImMessageRawRepository)

    # Retrieve some message data for testing
    sample_messages = []

    # Attempt to retrieve group chat messages by task type
    group_messages = await repo.get_by_task_type(task_type=3, limit=5)  # group chat
    if group_messages:
        sample_messages.extend(group_messages)
        logger.info("✅ Retrieved %d group chat messages", len(group_messages))

    # Attempt to retrieve private chat messages
    private_messages = await repo.get_by_task_type(task_type=2, limit=3)  # private chat
    if private_messages:
        sample_messages.extend(private_messages)
        logger.info("✅ Retrieved %d private chat messages", len(private_messages))

    # Retrieve bot messages
    bot_messages = await repo.get_by_task_type(task_type=4, limit=2)  # bot
    if bot_messages:
        sample_messages.extend(bot_messages)
        logger.info("✅ Retrieved %d bot messages", len(bot_messages))

    logger.info("✅ Total retrieved sample messages: %d", len(sample_messages))

    # Extract some useful test data
    room_ids = list(set([msg.roomId for msg in sample_messages if msg.roomId]))[:3]
    message_ids = [str(msg.id) for msg in sample_messages[:5]]
    msg_types = list(
        set([msg.msgType for msg in sample_messages if msg.msgType is not None])
    )[:3]

    logger.info("Available room IDs: %s", room_ids)
    logger.info("Available message IDs: %s", message_ids)
    logger.info("Available message types: %s", msg_types)

    return {
        "sample_messages": sample_messages,
        "room_ids": room_ids,
        "message_ids": message_ids,
        "msg_types": msg_types,
    }


async def test_get_by_id():
    """Test retrieving messages by ID"""
    logger.info("Starting test for retrieving messages by ID...")

    repo = get_bean_by_type(ImMessageRawRepository)
    sample_data = await get_sample_data()

    if not sample_data["message_ids"]:
        logger.warning("⚠️  No available message IDs for testing")
        return

    try:
        # Test retrieving existing messages
        for message_id in sample_data["message_ids"][:3]:
            message = await repo.get_by_id(message_id)
            if message:
                logger.info(
                    "✅ Successfully retrieved message: ID=%s, Content=%s, Room ID=%s",
                    message_id,
                    message.content[:50] if message.content else "No content",
                    message.roomId,
                )
            else:
                logger.info("ℹ️  Message does not exist: ID=%s", message_id)

        # Test retrieving non-existent message
        fake_id = "000000000000000000000000"  # Fake ObjectId
        fake_message = await repo.get_by_id(fake_id)
        assert fake_message is None, "Non-existent message should return None"
        logger.info("✅ Non-existent message correctly returns None")

    except Exception as e:
        logger.error("❌ Test for retrieving messages by ID failed: %s", e)
        raise

    logger.info("✅ Test for retrieving messages by ID completed")


async def test_get_by_room_id():
    """Test retrieving message list by room ID"""
    logger.info("Starting test for retrieving message list by room ID...")

    repo = get_bean_by_type(ImMessageRawRepository)
    sample_data = await get_sample_data()

    if not sample_data["room_ids"]:
        logger.warning("⚠️  No available room IDs for testing")
        return

    try:
        room_id = sample_data["room_ids"][0]

        # 1. Test basic query (without any filters)
        messages = await repo.get_by_room_id(room_id, limit=10)
        logger.info("✅ Basic query for room %s: Found %d messages", room_id, len(messages))

        if messages:
            # Display some message information
            for i, msg in enumerate(messages[:3]):
                logger.info(
                    "  Message %d: Type=%s, Time=%s, Content=%s",
                    i + 1,
                    msg.msgType,
                    to_iso_format(msg.createTime) if msg.createTime else "No time",
                    msg.content[:30] if msg.content else "No content",
                )

        # 2. Test filtering by message type
        if sample_data["msg_types"]:
            msg_type = sample_data["msg_types"][0]
            filtered_messages = await repo.get_by_room_id(
                room_id, msg_type=msg_type, limit=5
            )
            logger.info(
                "✅ Room %s filtered by message type %s: Found %d messages",
                room_id,
                msg_type,
                len(filtered_messages),
            )

        # 3. Test time range filtering
        current_time = get_now_with_timezone()
        start_time = current_time - timedelta(days=30)  # Last 30 days

        time_filtered = await repo.get_by_room_id(
            room_id, create_time_range=(start_time, current_time), limit=5
        )
        logger.info(
            "✅ Room %s filtered by time range (last 30 days): Found %d messages",
            room_id,
            len(time_filtered),
        )

        # 4. Test combined filtering
        if sample_data["msg_types"]:
            msg_type = sample_data["msg_types"][0]
            combined_filtered = await repo.get_by_room_id(
                room_id,
                msg_type=msg_type,
                create_time_range=(start_time, current_time),
                limit=3,
            )
            logger.info(
                "✅ Room %s combined filter (type + time): Found %d messages",
                room_id,
                len(combined_filtered),
            )

        # 5. Test pagination
        page1 = await repo.get_by_room_id(room_id, limit=3, skip=0)
        page2 = await repo.get_by_room_id(room_id, limit=3, skip=3)

        logger.info("✅ Pagination test: Page 1 has %d messages, Page 2 has %d messages", len(page1), len(page2))

        # Verify no duplicates in pagination results (if sufficient data)
        if len(page1) > 0 and len(page2) > 0:
            page1_ids = {str(msg.id) for msg in page1}
            page2_ids = {str(msg.id) for msg in page2}
            overlap = page1_ids & page2_ids
            if len(overlap) > 0:
                logger.warning("⚠️  Pagination results have duplicates (possibly due to unstable sorting): %s", overlap)
            else:
                logger.info("✅ No duplicates in pagination results")

        # 6. Test non-existent room ID
        fake_room_id = "non_existent_room_12345"
        empty_result = await repo.get_by_room_id(fake_room_id, limit=5)
        assert len(empty_result) == 0, "Non-existent room ID should return empty list"
        logger.info("✅ Non-existent room ID correctly returns empty list")

    except Exception as e:
        logger.error("❌ Test for retrieving message list by room ID failed: %s", e)
        raise

    logger.info("✅ Test for retrieving message list by room ID completed")


async def test_get_by_task_type():
    """Test retrieving message list by task type"""
    logger.info("Starting test for retrieving message list by task type...")

    repo = get_bean_by_type(ImMessageRawRepository)
    sample_data = await get_sample_data()

    try:
        # Test various task types
        task_types = [(2, "private chat"), (3, "group chat"), (4, "bot"), (9, "column")]

        for task_type, type_name in task_types:
            messages = await repo.get_by_task_type(task_type, limit=5)
            logger.info(
                "✅ Task type %d (%s): Found %d messages",
                task_type,
                type_name,
                len(messages),
            )

            # Verify returned messages are indeed of the specified task type
            for msg in messages:
                if msg.taskType is not None:
                    assert (
                        msg.taskType == task_type
                    ), f"Message task type mismatch: expected {task_type}, actual {msg.taskType}"

        # Test filtering combined with room ID
        if sample_data["room_ids"]:
            room_id = sample_data["room_ids"][0]

            # Retrieve group chat messages from this room
            room_group_messages = await repo.get_by_task_type(
                3, room_id=room_id, limit=3
            )
            logger.info(
                "✅ Group chat messages in room %s: Found %d messages", room_id, len(room_group_messages)
            )

            # Verify returned messages belong to the specified room and task type
            for msg in room_group_messages:
                if msg.roomId is not None:
                    assert (
                        msg.roomId == room_id
                    ), f"Message room ID mismatch: expected {room_id}, actual {msg.roomId}"
                if msg.taskType is not None:
                    assert (
                        msg.taskType == 3
                    ), f"Message task type mismatch: expected 3, actual {msg.taskType}"

        # Test non-existent task type
        invalid_messages = await repo.get_by_task_type(999, limit=5)
        logger.info("✅ Non-existent task type 999: Found %d messages", len(invalid_messages))

    except Exception as e:
        logger.error("❌ Test for retrieving message list by task type failed: %s", e)
        raise

    logger.info("✅ Test for retrieving message list by task type completed")


async def test_time_range_filtering():
    """Detailed test for time range filtering functionality"""
    logger.info("Starting test for time range filtering functionality...")

    repo = get_bean_by_type(ImMessageRawRepository)
    sample_data = await get_sample_data()

    if not sample_data["room_ids"]:
        logger.warning("⚠️  No available room IDs for time range testing")
        return

    try:
        room_id = sample_data["room_ids"][0]
        current_time = get_now_with_timezone()

        # Test different time ranges
        time_ranges = [
            (timedelta(days=1), "Last 1 day"),
            (timedelta(days=7), "Last 7 days"),
            (timedelta(days=30), "Last 30 days"),
            (timedelta(days=90), "Last 90 days"),
        ]

        for time_delta, description in time_ranges:
            start_time = current_time - time_delta

            messages = await repo.get_by_room_id(
                room_id, create_time_range=(start_time, current_time), limit=10
            )

            logger.info("✅ %s: Found %d messages", description, len(messages))

            # Verify returned messages are indeed within the specified time range
            for msg in messages:
                if msg.createTime:
                    assert (
                        msg.createTime >= start_time
                    ), f"Message time earlier than start time: {msg.createTime} < {start_time}"
                    assert (
                        msg.createTime <= current_time
                    ), f"Message time later than end time: {msg.createTime} > {current_time}"

        # Test case with only start time
        start_only = current_time - timedelta(days=7)
        messages_start_only = await repo.get_by_room_id(
            room_id, create_time_range=(start_only, None), limit=5
        )
        logger.info(
            "✅ Only start time specified (from 7 days ago to now): Found %d messages", len(messages_start_only)
        )

        # Test case with only end time
        end_only = current_time - timedelta(days=1)
        messages_end_only = await repo.get_by_room_id(
            room_id, create_time_range=(None, end_only), limit=5
        )
        logger.info(
            "✅ Only end time specified (before 1 day ago): Found %d messages", len(messages_end_only)
        )

    except Exception as e:
        logger.error("❌ Test for time range filtering functionality failed: %s", e)
        raise

    logger.info("✅ Time range filtering functionality test completed")


async def test_edge_cases():
    """Test edge cases and exception handling"""
    logger.info("Starting test for edge cases...")

    repo = get_bean_by_type(ImMessageRawRepository)

    try:
        # 1. Test empty string parameters
        empty_room_messages = await repo.get_by_room_id("", limit=1)
        logger.info("✅ Query with empty room ID: Found %d messages", len(empty_room_messages))

        # 2. Test extremely large limit value
        large_limit_messages = await repo.get_by_room_id("test_room", limit=10000)
        logger.info("✅ Query with extremely large limit: Found %d messages", len(large_limit_messages))

        # 3. Test negative limit (should be ignored or handled)
        try:
            negative_limit_messages = await repo.get_by_room_id("test_room", limit=-1)
            logger.info(
                "✅ Query with negative limit: Found %d messages", len(negative_limit_messages)
            )
        except ValueError as e:
            logger.info("ℹ️  Exception for negative limit query (expected behavior): %s", str(e))
        except Exception as e:
            logger.info("ℹ️  Other exception for negative limit query: %s", str(e))

        # 4. Test future time range
        future_time = get_now_with_timezone() + timedelta(days=1)
        future_messages = await repo.get_by_room_id(
            "test_room",
            create_time_range=(future_time, future_time + timedelta(hours=1)),
            limit=5,
        )
        assert len(future_messages) == 0, "Future time range should return empty list"
        logger.info("✅ Future time range query correctly returns empty list")

        # 5. Test invalid time range (start time later than end time)
        start_time = get_now_with_timezone()
        end_time = start_time - timedelta(hours=1)

        invalid_time_messages = await repo.get_by_room_id(
            "test_room", create_time_range=(start_time, end_time), limit=5
        )
        logger.info("✅ Query with invalid time range: Found %d messages", len(invalid_time_messages))

    except Exception as e:
        logger.error("❌ Test for edge cases failed: %s", e)
        raise

    logger.info("✅ Edge case test completed")


async def test_performance_and_pagination():
    """Test performance and pagination functionality"""
    logger.info("Starting test for performance and pagination functionality...")

    repo = get_bean_by_type(ImMessageRawRepository)
    sample_data = await get_sample_data()

    if not sample_data["room_ids"]:
        logger.warning("⚠️  No available room IDs for pagination testing")
        return

    try:
        room_id = sample_data["room_ids"][0]

        # Test query performance with large dataset
        start_time = datetime.now()
        large_result = await repo.get_by_room_id(room_id, limit=100)
        end_time = datetime.now()

        query_time = (end_time - start_time).total_seconds()
        logger.info(
            "✅ Query time for 100 messages: %.3f seconds, returned %d messages", query_time, len(large_result)
        )

        # Test pagination consistency
        page_size = 10
        all_pages = []

        for page in range(3):  # Retrieve first 3 pages
            page_messages = await repo.get_by_room_id(
                room_id, limit=page_size, skip=page * page_size
            )
            all_pages.extend(page_messages)
            logger.info("Page %d: %d messages", page + 1, len(page_messages))

            if len(page_messages) < page_size:
                logger.info("All available messages have been retrieved")
                break

        # Verify uniqueness of pagination results
        all_ids = [str(msg.id) for msg in all_pages]
        unique_ids = set(all_ids)

        if len(all_ids) != len(unique_ids):
            duplicates = len(all_ids) - len(unique_ids)
            logger.warning("⚠️  There are %d duplicate messages in pagination results", duplicates)
        else:
            logger.info("✅ No duplicates in pagination results")

        # Verify sorting consistency (by createTime in descending order)
        if len(all_pages) > 1:
            for i in range(len(all_pages) - 1):
                current_msg = all_pages[i]
                next_msg = all_pages[i + 1]

                if current_msg.createTime and next_msg.createTime:
                    assert (
                        current_msg.createTime >= next_msg.createTime
                    ), f"Sorting error: {current_msg.createTime} < {next_msg.createTime}"

            logger.info("✅ Pagination sorting consistency verification passed")

    except Exception as e:
        logger.error("❌ Test for performance and pagination functionality failed: %s", e)
        raise

    logger.info("✅ Performance and pagination functionality test completed")


async def run_all_tests():
    """Run all query tests"""
    logger.info("🚀 Starting ImMessage query interface tests...")

    try:
        await test_get_by_id()
        await test_get_by_room_id()
        await test_get_by_task_type()
        await test_time_range_filtering()
        await test_edge_cases()
        await test_performance_and_pagination()

        logger.info("✅ All query interface tests completed")

    except Exception as e:
        logger.error("❌ Error occurred during testing: %s", e)
        raise


if __name__ == "__main__":
    asyncio.run(run_all_tests())