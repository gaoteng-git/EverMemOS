#!/usr/bin/env python3
"""
memorize_offline offline memory processing test script

Usage:
    python tests/test_memorize_offline.py                                    # Default test for the last 7 days
    python tests/test_memorize_offline.py 3                                  # Test for the last 3 days
    python tests/test_memorize_offline.py 1 debug                           # Test for the last 1 day, with detailed output
    python tests/test_memorize_offline.py --from 2025-09-18 --to 2025-09-19 # Custom time range
    python tests/test_memorize_offline.py --from "2025-09-18 10:00" --to "2025-09-19 18:00" debug # Custom time + debug
    python tests/test_memorize_offline.py --extract-part personal_profile      # Extract only personal profile
"""

import asyncio
import sys
import argparse
from datetime import datetime, timedelta
from typing import Optional

# Add src directory to Python path

from api_specs.dtos.memory_command import MemorizeOfflineRequest
from biz_layer.tanka_memorize import memorize_offline
from common_utils.datetime_utils import get_now_with_timezone
from core.observation.logger import get_logger

# Get logger
logger = get_logger(__name__)


def parse_datetime(date_str: str) -> datetime:
    """
    Parse datetime string into datetime object

    Supported formats:
    - 2025-09-18
    - 2025-09-18 10:00
    - 2025-09-18 10:00:30
    """
    try:
        # Try different datetime formats
        formats = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                # Convert to timezone-aware datetime
                return get_now_with_timezone().replace(
                    year=dt.year,
                    month=dt.month,
                    day=dt.day,
                    hour=dt.hour,
                    minute=dt.minute,
                    second=dt.second,
                    microsecond=0,
                )
            except ValueError:
                continue

        raise ValueError(f"Unable to parse datetime format: {date_str}")

    except Exception as e:
        raise ValueError(f"Datetime parsing failed: {e}")


async def test_memorize_offline(
    days=None,
    start_time=None,
    end_time=None,
    debug: bool = False,
    extract_part: Optional[str] = None,
):
    """Test memorize_offline process"""

    # Determine time range
    if start_time and end_time:
        # Use custom time range
        memorize_from = start_time
        memorize_to = end_time
        logger.info("🚀 Testing memorize_offline process (custom time range)")
    elif days:
        # Use days range
        current_time = get_now_with_timezone()
        memorize_from = current_time - timedelta(days=days)
        memorize_to = current_time
        logger.info(f"🚀 Testing memorize_offline process (last {days} days)")
    else:
        # Default 7 days
        current_time = get_now_with_timezone()
        memorize_from = current_time - timedelta(days=7)
        memorize_to = current_time
        logger.info("🚀 Testing memorize_offline process (default last 7 days)")

    normalized_extract_part = None
    if extract_part:
        normalized = extract_part.strip().lower()
        if normalized and normalized != "all":
            normalized_extract_part = normalized

    request = MemorizeOfflineRequest(
        memorize_from=memorize_from,
        memorize_to=memorize_to,
        extract_part=normalized_extract_part,
    )

    logger.info(
        f"⏰ Time range: {request.memorize_from.strftime('%Y-%m-%d %H:%M')} ~ {request.memorize_to.strftime('%Y-%m-%d %H:%M')}"
    )
    if normalized_extract_part:
        logger.info(f"🎯 Extraction scope: {normalized_extract_part}")
    else:
        logger.info("🎯 Extraction scope: all")

    try:
        # Execute test
        start_time = datetime.now()
        result = await memorize_offline(request)
        end_time = datetime.now()

        duration = (end_time - start_time).total_seconds()

        logger.info(f"✅ Test completed! Duration: {duration:.2f} seconds")
        logger.info(f"📊 Extracted memories: {len(result) if result else 0} items")

        if result and len(result) > 0:
            # Statistics for memory types
            type_stats = {}
            group_stats = {}

            for memory in result:
                # Memory type statistics
                memory_type = (
                    memory.memory_type.value
                    if hasattr(memory.memory_type, 'value')
                    else str(memory.memory_type)
                )
                type_stats[memory_type] = type_stats.get(memory_type, 0) + 1

                # Group statistics
                if hasattr(memory, 'group_id') and memory.group_id:
                    group_stats[memory.group_id] = (
                        group_stats.get(memory.group_id, 0) + 1
                    )

            logger.info("📈 Memory type distribution:")
            for memory_type, count in type_stats.items():
                logger.info(f"   {memory_type}: {count} items")

            if debug and group_stats:
                logger.debug("👥 Group distribution:")
                for group_id, count in list(group_stats.items())[:5]:  # Show only first 5
                    logger.debug(f"   {group_id}: {count} items")
                if len(group_stats) > 5:
                    logger.debug(f"   ... and {len(group_stats) - 5} more groups")

            # Performance metrics
            if duration > 0:
                logger.info(f"⚡ Processing speed: {len(result) / duration:.2f} memories/second")

        elif debug:
            logger.debug("ℹ️  No data to process (possibly no new MemCell within the time range)")

        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=debug)
        return False


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='memorize_offline offline memory processing test',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage examples:
  %(prog)s                                    # Default test for last 7 days
  %(prog)s 3                                  # Test for last 3 days
  %(prog)s 1 debug                           # Test for last 1 day, with detailed output
  %(prog)s --from 2025-09-18 --to 2025-09-19 # Custom time range
  %(prog)s --from "2025-09-18 10:00" --to "2025-09-19 18:00" debug # Custom time + debug
  %(prog)s --extract-part personal_profile    # Extract only personal profile
        """,
    )

    # Positional arguments (for backward compatibility)
    parser.add_argument('days', nargs='?', type=int, help='Number of days to test (N days back from now)')
    parser.add_argument('mode', nargs='?', help='Mode: debug/verbose/d/v to enable debug output')

    # Custom time range
    parser.add_argument(
        '--from',
        dest='start_time',
        help='Start time (format: 2025-09-18 or "2025-09-18 10:00")',
    )
    parser.add_argument(
        '--to',
        dest='end_time',
        help='End time (format: 2025-09-19 or "2025-09-19 18:00")',
    )

    # Debug mode
    parser.add_argument('--debug', '-d', action='store_true', help='Enable debug mode')
    parser.add_argument(
        '--verbose', '-v', action='store_true', help='Enable verbose output (same as --debug)'
    )
    parser.add_argument(
        '--extract-part',
        choices=['all', 'personal_profile', 'group_profile'],
        help='Specify extraction scope, default is all',
    )

    args = parser.parse_args()

    # Determine debug mode
    debug = (
        args.debug
        or args.verbose
        or (args.mode and args.mode.lower() in ['debug', 'verbose', 'd', 'v'])
    )

    # Validate arguments
    days = args.days
    start_time = None
    end_time = None

    if args.start_time and args.end_time:
        # Custom time range mode
        try:
            start_time = parse_datetime(args.start_time)
            end_time = parse_datetime(args.end_time)

            if start_time >= end_time:
                logger.error("❌ Start time must be earlier than end time")
                return 1

        except ValueError as e:
            logger.error(f"❌ Invalid time format: {e}")
            logger.error(
                "Supported formats: 2025-09-18 or '2025-09-18 10:00' or '2025-09-18 10:00:30'"
            )
            return 1

    elif args.start_time or args.end_time:
        logger.error("❌ Both --from and --to parameters must be specified")
        return 1

    # If no days specified and no custom time, use default
    if not days and not (start_time and end_time):
        days = 7

    extract_part = args.extract_part
    extract_part_display = extract_part or 'all'
    if extract_part_display == 'all':
        extract_part_arg = None
    else:
        extract_part_arg = extract_part_display

    logger.info("🧪 memorize_offline offline memory processing test")
    if start_time and end_time:
        logger.info(
            f"📋 Parameters: Custom time range, Debug mode={'enabled' if debug else 'disabled'}, Extraction scope={extract_part_display}"
        )
    else:
        logger.info(
            f"📋 Parameters: {days} days, Debug mode={'enabled' if debug else 'disabled'}, Extraction scope={extract_part_display}"
        )
    logger.info("=" * 50)

    try:
        result = asyncio.run(
            test_memorize_offline(
                days=days,
                start_time=start_time,
                end_time=end_time,
                debug=debug,
                extract_part=extract_part_arg,
            )
        )
        if result:
            logger.info("\n🎉 Test succeeded!")
            return 0
        else:
            logger.error("\n💥 Test failed!")
            return 1
    except KeyboardInterrupt:
        logger.warning("\n⏹️  User interrupted test")
        return 2
    except Exception as e:
        logger.error(f"\n💥 Execution exception: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())