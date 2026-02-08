#!/usr/bin/env python3
"""
UserPromptSubmit Hook for EverMemOS
Automatically store user messages to EverMemOS
"""

import json
import sys
import os

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

    Claude Code provides hook data in two ways:
    1. Environment variable: CLAUDE_HOOK_INPUT (JSON string)
    2. stdin: JSON object

    Expected fields for UserPromptSubmit:
    - sessionId: string
    - prompt: string (user's input)
    - cwd: string (current working directory)
    - platform: string (claude-code or cursor)
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
    # Claude Code may also pass data as separate env vars
    return {
        'sessionId': os.environ.get('CLAUDE_SESSION_ID', 'unknown'),
        'prompt': os.environ.get('CLAUDE_USER_PROMPT', ''),
        'cwd': os.environ.get('CLAUDE_CWD', os.getcwd()),
        'platform': os.environ.get('CLAUDE_PLATFORM', 'claude-code'),
    }


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
        prompt = hook_data.get('prompt', '')
        cwd = hook_data.get('cwd', '')
        platform = hook_data.get('platform', 'claude-code')

        # Debug: log received data (to stderr, not stdout)
        print(f"[DEBUG] UserPrompt: platform={platform}, sessionId={session_id}, prompt_length={len(prompt)}, cwd={cwd}", file=sys.stderr)

        # Check if project is excluded from tracking (matches claude-mem behavior)
        if is_project_excluded(cwd):
            print(f"[DEBUG] Project excluded from tracking: {cwd}", file=sys.stderr)
            output = {"continue": True, "suppressOutput": True}
            print(json.dumps(output))
            sys.exit(0)

        # Handle image-only prompts (matches claude-mem behavior)
        # Use placeholder to preserve session tracking instead of skipping
        if not prompt or not prompt.strip():
            prompt = '[media prompt]'
            print(f"[DEBUG] Empty prompt detected, using placeholder: {prompt}", file=sys.stderr)

        # Get configuration
        config = get_env_config()

        # Use session_id as group_id to organize memories by session
        # If user has set EVERMEMOS_GROUP_ID explicitly, respect it
        if os.environ.get('EVERMEMOS_GROUP_ID') is None:
            config['group_id'] = f"session_{session_id}"

        print(f"[DEBUG] Using config: {config}", file=sys.stderr)

        client = EverMemOSClient(**config)

        # Store user message
        print(f"[DEBUG] Storing message to EverMemOS...", file=sys.stderr)
        result = client.store_message(
            content=prompt,
            role="user",
            sender_name="User"
        )

        # Log success
        print(f"[DEBUG] Message stored successfully: {result.get('message', 'OK')}", file=sys.stderr)

        # Return success
        output = {"continue": True, "suppressOutput": True}
        print(json.dumps(output))
        sys.exit(0)

    except Exception as e:
        # Log error but don't block user prompt
        print(f"[ERROR] Failed to store user message: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)

        # Return success anyway (graceful failure)
        output = {"continue": True, "suppressOutput": True}
        print(json.dumps(output))
        sys.exit(0)


if __name__ == "__main__":
    main()
