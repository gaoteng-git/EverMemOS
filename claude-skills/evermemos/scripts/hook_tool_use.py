#!/usr/bin/env python3
"""
PostToolUse Hook for EverMemOS
Record tool usage to EverMemOS for operation history
"""

import json
import sys
import os
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

    Expected fields for PostToolUse:
    - sessionId: string
    - toolName: string (name of the tool used)
    - toolInput: any (input to the tool)
    - toolResponse: any (output from the tool)
    - cwd: string (current working directory)
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
        'toolName': os.environ.get('CLAUDE_TOOL_NAME', ''),
        'toolInput': os.environ.get('CLAUDE_TOOL_INPUT', ''),
        'toolResponse': os.environ.get('CLAUDE_TOOL_RESPONSE', ''),
        'cwd': os.environ.get('CLAUDE_CWD', os.getcwd()),
    }


def get_env_config():
    """Get EverMemOS configuration from environment variables"""
    return {
        'base_url': os.environ.get('EVERMEMOS_BASE_URL', 'http://localhost:1995'),
        'user_id': os.environ.get('EVERMEMOS_USER_ID', 'claude_code_user'),
        'group_id': os.environ.get('EVERMEMOS_GROUP_ID', 'session_2026'),
    }


def truncate_text(text, max_length=500):
    """Truncate text to max_length characters"""
    if not text:
        return ""

    text_str = str(text)
    if len(text_str) <= max_length:
        return text_str

    return text_str[:max_length] + f"... (truncated, total length: {len(text_str)})"


def format_tool_observation(tool_name, tool_input, tool_response):
    """
    Format tool usage into observation message

    Returns a structured, human-readable message about tool usage
    """
    lines = []

    # Header
    lines.append(f"🔧 Tool Used: {tool_name}")
    lines.append(f"⏰ Time: {datetime.now().isoformat()}")
    lines.append("")

    # Input section
    if tool_input:
        input_str = truncate_text(tool_input, max_length=500)
        lines.append("📥 Input:")
        # Try to parse as JSON for better formatting
        try:
            if isinstance(tool_input, str):
                input_obj = json.loads(tool_input)
                input_str = json.dumps(input_obj, indent=2, ensure_ascii=False)
                # Truncate formatted JSON if too long
                if len(input_str) > 500:
                    input_str = input_str[:500] + "..."
        except:
            pass
        lines.append(input_str)
        lines.append("")

    # Response section
    if tool_response:
        response_str = truncate_text(tool_response, max_length=1000)
        lines.append("📤 Response:")
        # Try to parse as JSON for better formatting
        try:
            if isinstance(tool_response, str):
                response_obj = json.loads(tool_response)
                response_str = json.dumps(response_obj, indent=2, ensure_ascii=False)
                # Truncate formatted JSON if too long
                if len(response_str) > 1000:
                    response_str = response_str[:1000] + "..."
        except:
            pass
        lines.append(response_str)

    return "\n".join(lines)


def main():
    """Main execution"""
    try:
        # Read hook input
        hook_data = read_hook_input()

        session_id = hook_data.get('sessionId', 'unknown')
        tool_name = hook_data.get('toolName', '')
        tool_input = hook_data.get('toolInput', '')
        tool_response = hook_data.get('toolResponse', '')
        cwd = hook_data.get('cwd', '')

        # Debug: log received data
        print(f"[DEBUG] PostToolUse: sessionId={session_id}, tool={tool_name}, cwd={cwd}", file=sys.stderr)

        # Skip if no tool name (matches claude-mem validation)
        if not tool_name:
            print(f"[DEBUG] Skipping: no tool name", file=sys.stderr)
            output = {"continue": True, "suppressOutput": True}
            print(json.dumps(output))
            sys.exit(0)

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

        # Format tool observation
        observation_message = format_tool_observation(tool_name, tool_input, tool_response)

        print(f"[DEBUG] Storing tool observation to EverMemOS...", file=sys.stderr)
        print(f"[DEBUG] Message length: {len(observation_message)} chars", file=sys.stderr)

        # Store as user message with special sender name to indicate tool usage
        # Note: EverMemOS only includes role="user" messages in pending_messages
        result = client.store_message(
            content=observation_message,
            role="user",
            sender_name="Claude (Tool)"
        )

        # Log success
        print(f"[DEBUG] Tool observation stored successfully: {result.get('message', 'OK')}", file=sys.stderr)

        # Return success
        output = {"continue": True, "suppressOutput": True}
        print(json.dumps(output))
        sys.exit(0)

    except Exception as e:
        # Log error but don't block tool execution
        print(f"[ERROR] Failed to store tool observation: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)

        # Return success anyway (graceful failure)
        output = {"continue": True, "suppressOutput": True}
        print(json.dumps(output))
        sys.exit(0)


if __name__ == "__main__":
    main()
