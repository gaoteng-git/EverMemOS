"""
0G-Storage based KV-Storage implementation

Uses 0g-storage-client command-line tool for storage operations.
All values are Base64 encoded to avoid \\n and , issues.

Key Format: {collection_name}:{document_id}
Example: "episodic_memories:6979da5797f9041fc0aa063f"

Environment Variables Required:
- ZEROG_WALLET_KEY: Wallet private key (IMPORTANT: Keep secure!)
"""

import asyncio
import json
import os
from typing import Optional, Dict, List
from core.observation.logger import get_logger
from core.di.decorators import component
from .kv_storage_interface import KVStorageInterface
from .encoding_utils import (
    encode_value_for_zerog,
    decode_value_from_zerog,
    decode_values_batch
)

logger = get_logger(__name__)


@component("zerog_kv_storage")
class ZeroGKVStorage(KVStorageInterface):
    """
    0G-Storage based KV-Storage implementation

    Uses 0g-storage-client command-line tool for storage operations.
    All values are Base64 encoded to avoid \\n and , issues.

    Note:
    - All documents share a unified stream-id
    - Keys use format: {collection_name}:{document_id}
    - Delete is implemented as writing empty string
    """

    def __init__(
        self,
        nodes: str,                    # "http://35.236.80.213:5678,http://34.102.76.235:5678"
        stream_id: str,                # Unified stream ID for all collections
        rpc_url: str,                  # "https://evmrpc-testnet.0g.ai"
        read_node: str,                # "http://34.31.1.26:6789" (read operations)
        timeout: int = 30,             # Command timeout in seconds
        max_retries: int = 3           # Max retry attempts
    ):
        self.nodes = nodes
        self.stream_id = stream_id
        self.rpc_url = rpc_url
        self.read_node = read_node
        self.timeout = timeout
        self.max_retries = max_retries

        # Get wallet private key from environment variable (SECURE!)
        self.wallet_private_key = os.getenv('ZEROG_WALLET_KEY')
        if not self.wallet_private_key:
            raise ValueError("ZEROG_WALLET_KEY environment variable is required")

        logger.info(
            f"✅ ZeroGKVStorage initialized: stream_id={stream_id}, "
            f"nodes={nodes.split(',')[0]}..., timeout={timeout}s"
        )


    async def get(self, key: str) -> Optional[str]:
        """
        Get value by key

        Args:
            key: Full key including collection prefix (e.g., "episodic_memories:123")

        Returns:
            JSON string or None if not found
        """
        try:
            # Execute read command
            cmd = [
                '0g-storage-client', 'kv-read',
                '--node', self.read_node,
                '--stream-id', self.stream_id,
                '--stream-keys', key
            ]

            result = await self._execute_command(cmd)

            # Parse JSON response: {"key1":"value1"}
            response = json.loads(result)
            encoded_value = response.get(key)

            if encoded_value is None or encoded_value == "":
                # Key not found or deleted
                return None

            # Base64 decode
            json_value = decode_value_from_zerog(encoded_value)
            logger.debug(f"✅ Get key: {key} ({len(json_value)} bytes)")
            return json_value

        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse response for key {key}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Failed to get key {key}: {e}")
            return None


    async def put(self, key: str, value: str) -> bool:
        """
        Store key-value pair

        Args:
            key: Full key including collection prefix (e.g., "episodic_memories:123")
            value: JSON string to store

        Returns:
            True if successful
        """
        try:
            # Base64 encode value
            encoded_value = encode_value_for_zerog(value)

            # Execute write command
            cmd = [
                '0g-storage-client', 'kv-write',
                '--node', self.nodes,
                '--key', self.wallet_private_key,
                '--stream-id', self.stream_id,
                '--stream-keys', key,
                '--stream-values', encoded_value,
                '--url', self.rpc_url
            ]

            await self._execute_command(cmd)
            logger.debug(f"✅ Put key: {key} ({len(value)} bytes)")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to put key {key}: {e}")
            return False


    async def delete(self, key: str) -> bool:
        """
        Delete by key (implemented as writing empty string)

        Args:
            key: Full key including collection prefix

        Returns:
            True if successful
        """
        try:
            # Delete by writing empty string
            cmd = [
                '0g-storage-client', 'kv-write',
                '--node', self.nodes,
                '--key', self.wallet_private_key,
                '--stream-id', self.stream_id,
                '--stream-keys', key,
                '--stream-values', '',  # Empty string for deletion
                '--url', self.rpc_url
            ]

            await self._execute_command(cmd)
            logger.debug(f"✅ Delete key: {key}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to delete key {key}: {e}")
            return False


    async def batch_get(self, keys: List[str]) -> Dict[str, str]:
        """
        Batch get values

        Args:
            keys: List of keys (each with collection prefix)

        Returns:
            Dict mapping key to JSON string
        """
        if not keys:
            return {}

        try:
            # Join keys with comma
            keys_str = ','.join(keys)

            # Execute read command
            cmd = [
                '0g-storage-client', 'kv-read',
                '--node', self.read_node,
                '--stream-id', self.stream_id,
                '--stream-keys', keys_str
            ]

            result = await self._execute_command(cmd)

            # Parse JSON response: {"key1":"value1","key2":"value2"}
            encoded_response = json.loads(result)

            # Base64 decode all values (skip empty values = deleted items)
            decoded_response = decode_values_batch(encoded_response)

            logger.debug(f"✅ Batch get {len(decoded_response)}/{len(keys)} keys")
            return decoded_response

        except Exception as e:
            logger.error(f"❌ Failed to batch get {len(keys)} keys: {e}")
            return {}


    async def batch_delete(self, keys: List[str]) -> int:
        """
        Batch delete keys (implemented as writing empty strings)

        Args:
            keys: List of keys to delete

        Returns:
            Number of keys successfully deleted
        """
        if not keys:
            return 0

        try:
            # Join keys with comma
            keys_str = ','.join(keys)

            # Join empty values with comma: ",," for 3 keys
            values_str = ','.join([''] * len(keys))

            # Execute batch write with empty values
            cmd = [
                '0g-storage-client', 'kv-write',
                '--node', self.nodes,
                '--key', self.wallet_private_key,
                '--stream-id', self.stream_id,
                '--stream-keys', keys_str,
                '--stream-values', values_str,  # Empty strings separated by commas
                '--url', self.rpc_url
            ]

            await self._execute_command(cmd)
            logger.debug(f"✅ Batch delete {len(keys)} keys")
            return len(keys)

        except Exception as e:
            logger.error(f"❌ Failed to batch delete {len(keys)} keys: {e}")
            return 0


    async def _execute_command(self, cmd: List[str]) -> str:
        """
        Execute 0g-storage-client command with retry and exponential backoff

        Args:
            cmd: Command and arguments as list

        Returns:
            Command stdout output

        Raises:
            RuntimeError: If command fails after retries
        """
        for attempt in range(self.max_retries):
            try:
                # Create subprocess
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                # Wait with timeout
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout
                )

                # Check return code
                if process.returncode != 0:
                    error_msg = stderr.decode('utf-8').strip() if stderr else 'Unknown error'
                    raise RuntimeError(
                        f"Command failed with code {process.returncode}: {error_msg}"
                    )

                result = stdout.decode('utf-8').strip()

                if attempt > 0:
                    logger.info(f"✅ Command succeeded on attempt {attempt + 1}")

                return result

            except asyncio.TimeoutError:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                logger.warning(
                    f"⚠️  Command timeout (attempt {attempt + 1}/{self.max_retries}), "
                    f"retrying in {wait_time}s..."
                )
                if attempt == self.max_retries - 1:
                    raise RuntimeError(
                        f"Command timed out after {self.max_retries} attempts "
                        f"(timeout={self.timeout}s)"
                    )
                await asyncio.sleep(wait_time)

            except Exception as e:
                wait_time = 2 ** attempt
                logger.warning(
                    f"⚠️  Command failed (attempt {attempt + 1}/{self.max_retries}): {e}, "
                    f"retrying in {wait_time}s..."
                )
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(wait_time)


__all__ = ["ZeroGKVStorage"]
