"""
Base64 encoding utilities for 0G-Storage

0G-Storage does not support values containing '\n' and ','.
This module provides encoding/decoding functions using Base64.
"""

import base64
import json
from typing import Dict
from core.observation.logger import get_logger

logger = get_logger(__name__)


def encode_value_for_zerog(json_string: str) -> str:
    """
    Encode JSON string to Base64 for 0G-Storage

    Process:
    1. Parse JSON to validate
    2. Compact JSON (remove whitespace, ensure no \n)
    3. Base64 encode

    Args:
        json_string: Original JSON string (may contain \n and ,)

    Returns:
        Base64 encoded string (safe for 0G-Storage, no \n or ,)

    Example:
        >>> encode_value_for_zerog('{"user_id":"123","name":"test"}')
        'eyJ1c2VyX2lkIjoiMTIzIiwibmFtZSI6InRlc3QifQ=='
    """
    try:
        # Parse to validate + compact (remove all whitespace)
        data = json.loads(json_string)
        compact_json = json.dumps(data, separators=(',', ':'), ensure_ascii=False)

        # Base64 encode
        encoded_bytes = base64.b64encode(compact_json.encode('utf-8'))
        encoded_string = encoded_bytes.decode('ascii')

        logger.debug(f"Encoded value: {len(json_string)} bytes -> {len(encoded_string)} bytes")
        return encoded_string
    except Exception as e:
        logger.error(f"Failed to encode value: {e}")
        raise


def decode_value_from_zerog(encoded_string: str) -> str:
    """
    Decode Base64 string from 0G-Storage to JSON

    Args:
        encoded_string: Base64 encoded string from 0G-Storage

    Returns:
        Original JSON string

    Example:
        >>> decode_value_from_zerog('eyJ1c2VyX2lkIjoiMTIzIiwibmFtZSI6InRlc3QifQ==')
        '{"user_id":"123","name":"test"}'
    """
    try:
        # Base64 decode
        decoded_bytes = base64.b64decode(encoded_string.encode('ascii'))
        json_string = decoded_bytes.decode('utf-8')

        # Validate JSON
        json.loads(json_string)

        return json_string
    except Exception as e:
        logger.error(f"Failed to decode value: {e}")
        raise


def encode_values_batch(values: Dict[str, str]) -> Dict[str, str]:
    """
    Batch encode multiple values

    Args:
        values: Dict mapping key to JSON string

    Returns:
        Dict mapping key to Base64 encoded string
    """
    encoded = {}
    for key, val in values.items():
        try:
            encoded[key] = encode_value_for_zerog(val)
        except Exception as e:
            logger.warning(f"Failed to encode key {key}: {e}")
            # Skip failed encoding
    return encoded


def decode_values_batch(encoded_values: Dict[str, str]) -> Dict[str, str]:
    """
    Batch decode multiple values

    Args:
        encoded_values: Dict mapping key to Base64 string

    Returns:
        Dict mapping key to JSON string
    """
    decoded = {}
    for key, val in encoded_values.items():
        try:
            # Skip empty values (deleted items)
            if not val or val == "":
                continue
            decoded[key] = decode_value_from_zerog(val)
        except Exception as e:
            logger.warning(f"Failed to decode key {key}: {e}")
            # Skip failed decoding
    return decoded


__all__ = [
    "encode_value_for_zerog",
    "decode_value_from_zerog",
    "encode_values_batch",
    "decode_values_batch"
]
