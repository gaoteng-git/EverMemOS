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
        lines.append("📥 Input:")
        # Handle both dict and string formats
        if isinstance(tool_input, dict):
            input_str = json.dumps(tool_input, indent=2, ensure_ascii=False)
            if len(input_str) > 500:
                input_str = input_str[:500] + "..."
        elif isinstance(tool_input, str):
            try:
                input_obj = json.loads(tool_input)
                input_str = json.dumps(input_obj, indent=2, ensure_ascii=False)
                if len(input_str) > 500:
                    input_str = input_str[:500] + "..."
            except:
                input_str = truncate_text(tool_input, max_length=500)
        else:
            input_str = truncate_text(str(tool_input), max_length=500)
        lines.append(input_str)
        lines.append("")

    # Response section
    if tool_response:
        lines.append("📤 Response:")
        # Handle both dict and string formats
        if isinstance(tool_response, dict):
            # For dict, extract stdout or convert to JSON
            if 'stdout' in tool_response:
                response_str = truncate_text(tool_response['stdout'], max_length=1000)
            else:
                response_str = json.dumps(tool_response, indent=2, ensure_ascii=False)
                if len(response_str) > 1000:
                    response_str = response_str[:1000] + "..."
        elif isinstance(tool_response, str):
            try:
                response_obj = json.loads(tool_response)
                response_str = json.dumps(response_obj, indent=2, ensure_ascii=False)
                if len(response_str) > 1000:
                    response_str = response_str[:1000] + "..."
            except:
                response_str = truncate_text(tool_response, max_length=1000)
        else:
            response_str = truncate_text(str(tool_response), max_length=1000)
        lines.append(response_str)

    return "\n".join(lines)


def find_transcript_path(session_id):
    """
    Find transcript file path for given session_id

    Args:
        session_id: Session identifier

    Returns:
        str: Path to transcript file, or None if not found
    """
    try:
        # Transcript files are typically in ~/.claude/projects/<project>/<session_id>.jsonl
        project_dir = os.environ.get('CLAUDE_PROJECT_DIR')
        if not project_dir:
            return None

        # Look for transcript file
        claude_dir = os.path.expanduser('~/.claude/projects')

        # Try to find by session_id
        for root, dirs, files in os.walk(claude_dir):
            for file in files:
                if file.startswith(session_id) and file.endswith('.jsonl'):
                    return os.path.join(root, file)

        return None
    except Exception as e:
        print(f"[WARNING] Failed to find transcript: {e}", file=sys.stderr)
        return None


def extract_last_assistant_message_from_transcript(transcript_path):
    """
    Extract last assistant message with text content
    (Simplified version without system-reminder stripping for tool hook)
    """
    if not transcript_path or not os.path.exists(transcript_path):
        return None

    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()

        if not content:
            return None

        lines = content.split('\n')

        # Iterate from last to first
        for line in reversed(lines):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if entry.get('type') != 'assistant':
                continue

            msg_content = entry.get('message', {}).get('content')
            if not msg_content:
                continue

            text = ''
            if isinstance(msg_content, str):
                text = msg_content
            elif isinstance(msg_content, list):
                text_parts = []
                for item in msg_content:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        text_parts.append(item.get('text', ''))
                text = '\n'.join(text_parts)

            if text and text.strip():
                return text.strip()

        return None
    except Exception as e:
        print(f"[WARNING] Failed to extract message: {e}", file=sys.stderr)
        return None


def main():
    """Main execution"""
    # Enable detailed logging to file for debugging
    log_file = "/tmp/post_tool_use_hook.log"

    try:
        # Read hook input
        hook_data = read_hook_input()

        # Claude Code uses snake_case for parameter names
        session_id = hook_data.get('session_id') or hook_data.get('sessionId', 'unknown')
        tool_name = hook_data.get('tool_name') or hook_data.get('toolName', '')
        tool_input = hook_data.get('tool_input') or hook_data.get('toolInput', '')
        tool_response = hook_data.get('tool_response') or hook_data.get('toolResponse', '')
        cwd = hook_data.get('cwd', '')
        transcript_path = hook_data.get('transcript_path')  # May not be provided

        # Debug: log received data
        print(f"[DEBUG] PostToolUse: sessionId={session_id}, tool={tool_name}, cwd={cwd}", file=sys.stderr)

        # Also log to file
        with open(log_file, 'a') as f:
            f.write(f"\n=== PostToolUse Hook {datetime.now().isoformat()} ===\n")
            f.write(f"SessionId: {session_id}\n")
            f.write(f"Tool: {tool_name}\n")
            f.write(f"CWD: {cwd}\n")
            f.write(f"Has transcript_path: {bool(transcript_path)}\n")
            f.write(f"ALL hook_data keys: {list(hook_data.keys())}\n")
            f.write(f"Full hook_data: {json.dumps(hook_data, indent=2)}\n")

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

        # OPTION 2: Also try to extract and store assistant's text response
        # This provides a backup mechanism if Stop hook misses some responses
        print(f"[DEBUG] Attempting to extract assistant response...", file=sys.stderr)

        if not transcript_path:
            transcript_path = find_transcript_path(session_id)
            print(f"[DEBUG] Found transcript path: {transcript_path}", file=sys.stderr)

        if transcript_path:
            import time
            time.sleep(0.3)  # Small delay to let transcript flush

            assistant_message = extract_last_assistant_message_from_transcript(transcript_path)

            if assistant_message and len(assistant_message) > 20:  # Only store substantial messages
                print(f"[DEBUG] Found assistant message ({len(assistant_message)} chars), storing...", file=sys.stderr)

                # Store assistant's response
                result = client.store_message(
                    content=assistant_message,
                    role="user",
                    sender_name="Claude (Response)"
                )
                print(f"[DEBUG] Assistant response stored via PostToolUse: {result.get('message', 'OK')}", file=sys.stderr)
            else:
                print(f"[DEBUG] No substantial assistant message found", file=sys.stderr)
        else:
            print(f"[DEBUG] No transcript path available", file=sys.stderr)

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
