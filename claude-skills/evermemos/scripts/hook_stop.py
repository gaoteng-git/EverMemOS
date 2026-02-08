#!/usr/bin/env python3
"""
Stop Hook for EverMemOS
Capture Claude's text output after each response (every turn)
"""

import json
import sys
import os
import re
from datetime import datetime

# Add current directory to path to import evermemos_client
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from evermemos_client import EverMemOSClient
    from evermemos_config import is_project_excluded
except ImportError as e:
    # If import fails, exit gracefully
    print(json.dumps({
        "continue": True,
        "suppressOutput": True
    }))
    sys.exit(0)


def read_hook_input():
    """
    Read hook input from Claude Code

    Expected fields for Stop:
    - sessionId: string
    - cwd: string (current working directory)
    - transcript_path: string (path to transcript JSONL file)
    """
    # Method 1: Try environment variable first
    hook_input_env = os.environ.get('CLAUDE_HOOK_INPUT')
    if hook_input_env:
        try:
            return json.loads(hook_input_env)
        except json.JSONDecodeError:
            pass

    # Method 2: Try reading from stdin
    if not sys.stdin.isatty():
        try:
            return json.load(sys.stdin)
        except json.JSONDecodeError:
            pass

    # Method 3: Build from individual environment variables
    return {
        'sessionId': os.environ.get('CLAUDE_SESSION_ID', 'unknown'),
        'cwd': os.environ.get('CLAUDE_CWD', os.getcwd()),
        'transcript_path': os.environ.get('CLAUDE_TRANSCRIPT_PATH', None),
    }


def extract_last_assistant_message(transcript_path):
    """
    Extract last assistant message from transcript JSONL file

    This function replicates the logic from claude-mem:
    src/shared/transcript-parser.ts::extractLastMessage()

    Args:
        transcript_path: Path to transcript JSONL file

    Returns:
        str: Claude's text output (without tool_use blocks and system-reminders)
        None: If no assistant message found or file doesn't exist
    """
    if not transcript_path or not os.path.exists(transcript_path):
        return None

    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()

        if not content:
            return None

        lines = content.split('\n')

        # Iterate from last to first (reverse order)
        for line in reversed(lines):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Check if this is an assistant message
            if entry.get('type') != 'assistant':
                continue

            # Extract message content
            message = entry.get('message', {})
            msg_content = message.get('content')

            if not msg_content:
                continue

            # Handle different content formats
            text = ''

            if isinstance(msg_content, str):
                # String format: use directly
                text = msg_content
            elif isinstance(msg_content, list):
                # Array format: extract only text blocks (filter out tool_use)
                text_parts = []
                for item in msg_content:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        text_parts.append(item.get('text', ''))
                text = '\n'.join(text_parts)
            else:
                # Unknown format, skip
                continue

            # Strip system-reminder tags (same as claude-mem)
            text = re.sub(r'<system-reminder>[\s\S]*?</system-reminder>', '', text)

            # Normalize multiple newlines
            text = re.sub(r'\n{3,}', '\n\n', text).strip()

            return text if text else None

        # No assistant message found
        return None

    except Exception as e:
        print(f"[WARNING] Failed to extract assistant message: {e}", file=sys.stderr)
        return None


def get_env_config():
    """Get EverMemOS configuration from environment variables"""
    return {
        'base_url': os.environ.get('EVERMEMOS_BASE_URL', 'http://localhost:1995'),
        'user_id': os.environ.get('EVERMEMOS_USER_ID', 'claude_code_user'),
        'group_id': os.environ.get('EVERMEMOS_GROUP_ID', 'session_2026'),
    }


def main():
    """Main execution"""
    try:
        # Read hook input
        hook_data = read_hook_input()

        session_id = hook_data.get('sessionId', 'unknown')
        cwd = hook_data.get('cwd', '')
        transcript_path = hook_data.get('transcript_path')

        # Debug: log received data
        print(f"[DEBUG] Stop: sessionId={session_id}, cwd={cwd}", file=sys.stderr)
        print(f"[DEBUG] Stop: transcript_path={transcript_path}", file=sys.stderr)

        # Check if project is excluded from tracking (matches claude-mem behavior)
        if is_project_excluded(cwd):
            print(f"[DEBUG] Project excluded from tracking: {cwd}", file=sys.stderr)
            output = {"continue": True, "suppressOutput": True}
            print(json.dumps(output))
            sys.exit(0)

        # Get configuration
        config = get_env_config()

        # Use session_id as group_id to organize by session
        if os.environ.get('EVERMEMOS_GROUP_ID') is None:
            config['group_id'] = f"session_{session_id}"

        print(f"[DEBUG] Using config: {config}", file=sys.stderr)

        client = EverMemOSClient(**config)

        # Extract Claude's text output from transcript
        if transcript_path:
            print(f"[DEBUG] Extracting assistant message from transcript...", file=sys.stderr)

            claude_output = extract_last_assistant_message(transcript_path)

            if claude_output:
                print(f"[DEBUG] Extracted assistant output: {len(claude_output)} chars", file=sys.stderr)

                # Store Claude's text output
                # Use role="user" because EverMemOS only includes user messages in pending_messages
                result = client.store_message(
                    content=claude_output,
                    role="user",
                    sender_name="Claude (Response)"
                )

                print(f"[DEBUG] Claude output stored successfully: {result.get('message', 'OK')}", file=sys.stderr)
            else:
                print(f"[DEBUG] No assistant message found in transcript", file=sys.stderr)
        else:
            print(f"[DEBUG] No transcript_path provided, skipping assistant message extraction", file=sys.stderr)

        # Return success
        output = {"continue": True, "suppressOutput": True}
        print(json.dumps(output))
        sys.exit(0)

    except Exception as e:
        # Log error but don't block Claude from stopping
        print(f"[ERROR] Failed to capture Claude output: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)

        # Return success anyway (graceful failure)
        output = {"continue": True, "suppressOutput": True}
        print(json.dumps(output))
        sys.exit(0)


if __name__ == "__main__":
    main()
