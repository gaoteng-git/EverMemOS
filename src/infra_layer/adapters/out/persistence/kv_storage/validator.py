"""
MemCell Data Validation Utilities

Tools for comparing MemCell data between MongoDB and KV-Storage,
and logging inconsistencies for debugging and monitoring.
"""

import json
from typing import Tuple, Optional, Any, Dict
from datetime import datetime, timedelta
from core.observation.logger import get_logger

logger = get_logger(__name__)

# Time fields that may have microsecond precision differences
TIMESTAMP_FIELDS = {'timestamp', 'created_at', 'updated_at'}
# Maximum allowed time difference (1 second tolerance for time fields)
MAX_TIME_DIFF = timedelta(seconds=1)


def compare_memcell_data(
    mongo_json: str, kv_json: str
) -> Tuple[bool, Optional[str]]:
    """
    Compare MemCell data from MongoDB and KV-Storage.

    This function compares two JSON strings representing the same MemCell document.
    It handles field order differences by parsing JSON and comparing as dicts.

    Args:
        mongo_json: JSON string from MongoDB (via memcell.model_dump_json())
        kv_json: JSON string from KV-Storage

    Returns:
        Tuple of (is_consistent, difference_description)
        - is_consistent: True if data matches, False otherwise
        - difference_description: None if consistent, detailed diff string if not
    """
    try:
        # Option 1: Direct string comparison (strictest, catches field order issues)
        if mongo_json == kv_json:
            return (True, None)

        # Option 2: Parse and compare as dicts (handles field order differences)
        try:
            mongo_dict = json.loads(mongo_json)
            kv_dict = json.loads(kv_json)
        except json.JSONDecodeError as e:
            return (False, f"JSON parsing error: {str(e)}")

        if mongo_dict == kv_dict:
            # Data is same, just field order differs
            return (True, None)

        # Find and report differences
        diff_desc = _find_differences(mongo_dict, kv_dict)
        if diff_desc:
            # Has actual differences
            return (False, diff_desc)
        else:
            # All differences are within tolerance (e.g., timestamp precision)
            return (True, None)

    except Exception as e:
        logger.error(f"Failed to compare memcell data: {e}", exc_info=True)
        return (False, f"Comparison error: {str(e)}")


def _is_timestamp_field(key: str) -> bool:
    """Check if a field name is a timestamp field."""
    return key in TIMESTAMP_FIELDS


def _compare_timestamps(val1: str, val2: str) -> bool:
    """
    Compare two timestamp strings with tolerance for microsecond precision differences.

    Args:
        val1: First timestamp string (MongoDB)
        val2: Second timestamp string (KV-Storage)

    Returns:
        True if timestamps are within tolerance, False otherwise
    """
    try:
        # Parse ISO format timestamps
        dt1 = datetime.fromisoformat(val1.replace('Z', '+00:00'))
        dt2 = datetime.fromisoformat(val2.replace('Z', '+00:00'))

        # Check if difference is within tolerance
        diff = abs(dt1 - dt2)
        return diff <= MAX_TIME_DIFF
    except (ValueError, AttributeError):
        # If parsing fails, fall back to string comparison
        return False


def _find_differences(dict1: Dict[str, Any], dict2: Dict[str, Any], path: str = "") -> str:
    """
    Recursively find differences between two dictionaries.

    Args:
        dict1: First dictionary (MongoDB data)
        dict2: Second dictionary (KV-Storage data)
        path: Current path in nested structure (for error reporting)

    Returns:
        String describing all differences found
    """
    differences = []

    # Check for key differences
    keys1 = set(dict1.keys())
    keys2 = set(dict2.keys())

    only_in_mongo = keys1 - keys2
    only_in_kv = keys2 - keys1

    if only_in_mongo:
        differences.append(
            f"Keys only in MongoDB at {path or 'root'}: {sorted(only_in_mongo)}"
        )
    if only_in_kv:
        differences.append(
            f"Keys only in KV at {path or 'root'}: {sorted(only_in_kv)}"
        )

    # Check for value differences in common keys
    for key in keys1 & keys2:
        val1 = dict1[key]
        val2 = dict2[key]
        current_path = f"{path}.{key}" if path else key

        if isinstance(val1, dict) and isinstance(val2, dict):
            # Recursively compare nested dicts
            nested_diff = _find_differences(val1, val2, current_path)
            if nested_diff:
                differences.append(nested_diff)
        elif isinstance(val1, list) and isinstance(val2, list):
            # Compare lists
            if len(val1) != len(val2):
                differences.append(
                    f"List length mismatch at {current_path}: "
                    f"MongoDB={len(val1)}, KV={len(val2)}"
                )
            elif val1 != val2:
                differences.append(
                    f"List content mismatch at {current_path}"
                )
        elif val1 != val2:
            # Special handling for timestamp fields
            if _is_timestamp_field(key) and isinstance(val1, str) and isinstance(val2, str):
                if _compare_timestamps(val1, val2):
                    # Timestamps are within tolerance, skip this difference
                    continue

            # Direct value comparison
            # Truncate long values for readability
            val1_str = str(val1)[:100]
            val2_str = str(val2)[:100]
            differences.append(
                f"Value mismatch at {current_path}: "
                f"MongoDB={val1_str!r}, KV={val2_str!r}"
            )

    return "; ".join(differences) if differences else ""


def log_inconsistency(event_id: str, details: Dict[str, Any]) -> None:
    """
    Log data inconsistency to a dedicated logger for monitoring.

    This function logs detailed information about data inconsistencies
    between MongoDB and KV-Storage. These logs can be used for:
    - Debugging synchronization issues
    - Monitoring data quality
    - Alerting on critical inconsistencies

    Args:
        event_id: MemCell event_id where inconsistency was detected
        details: Dictionary containing inconsistency details (e.g., difference description)
    """
    try:
        # Log as ERROR level for visibility
        logger.error(
            f"[DATA_INCONSISTENCY] event_id={event_id}\n"
            f"Details: {json.dumps(details, indent=2, ensure_ascii=False, default=str)}"
        )

        # TODO: Consider adding:
        # - Writing to a separate inconsistency log file
        # - Sending metrics to monitoring system
        # - Triggering alerts for critical inconsistencies

    except Exception as e:
        logger.error(f"Failed to log inconsistency for {event_id}: {e}")


def validate_json_serialization(data: str) -> Tuple[bool, Optional[str]]:
    """
    Validate that a string is valid JSON.

    Args:
        data: String to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        json.loads(data)
        return (True, None)
    except json.JSONDecodeError as e:
        return (False, str(e))
    except Exception as e:
        return (False, f"Unexpected error: {str(e)}")
