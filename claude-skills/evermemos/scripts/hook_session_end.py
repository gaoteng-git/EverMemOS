#!/usr/bin/env python3
"""
SessionEnd Hook for EverMemOS
Generate session summary when Claude Code session terminates (only once)
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

    Expected fields for SessionEnd:
    - sessionId: string
    - cwd: string (current working directory)
    - reason: string (why the session ended)
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
        'reason': os.environ.get('CLAUDE_SESSION_END_REASON', 'other'),
    }


def get_env_config():
    """Get EverMemOS configuration from environment variables"""
    return {
        'base_url': os.environ.get('EVERMEMOS_BASE_URL', 'http://localhost:1995'),
        'user_id': os.environ.get('EVERMEMOS_USER_ID', 'claude_code_user'),
        'group_id': os.environ.get('EVERMEMOS_GROUP_ID', 'session_2026'),
    }


def generate_session_summary(session_id, reason, client):
    """
    Generate a summary of the entire session

    Args:
        session_id: Session identifier
        reason: Why the session ended
        client: EverMemOSClient instance

    Returns:
        str: Summary text
    """
    try:
        # Fetch all messages from this session via search API
        # Use empty query to get all messages (max 100 due to API limit)
        response = client.search_memories("", method="hybrid", top_k=100)
        result = response.get('result', {})

        # Get episodic memories and pending messages
        memories_groups = result.get('memories', [])
        pending_messages = result.get('pending_messages', [])

        # Extract memories from groups
        all_memories = []
        for group_dict in memories_groups:
            for group_name, group_memories in group_dict.items():
                all_memories.extend(group_memories)

        # Count different types of messages
        user_messages = 0
        claude_responses = 0
        tool_observations = 0
        system_messages = 0

        for msg in pending_messages:
            sender_name = msg.get('sender_name', '')
            if 'Tool' in sender_name:
                tool_observations += 1
            elif 'Claude (Response)' in sender_name:
                claude_responses += 1
            elif 'System' in sender_name:
                system_messages += 1
            else:
                user_messages += 1

        # Calculate conversation turns (user input + Claude response pairs)
        conversation_turns = min(user_messages, claude_responses)

        # Get time span
        first_time = None
        last_time = None

        if pending_messages:
            times = [msg.get('message_create_time', '') for msg in pending_messages if msg.get('message_create_time')]
            if times:
                times_sorted = sorted(times)
                first_time = times_sorted[0]
                last_time = times_sorted[-1]

        # Calculate session duration
        duration_str = "Unknown"
        if first_time and last_time:
            try:
                from dateutil import parser
                start = parser.parse(first_time)
                end = parser.parse(last_time)
                duration = end - start
                hours = int(duration.total_seconds() // 3600)
                minutes = int((duration.total_seconds() % 3600) // 60)
                seconds = int(duration.total_seconds() % 60)
                if hours > 0:
                    duration_str = f"{hours}h {minutes}m {seconds}s"
                elif minutes > 0:
                    duration_str = f"{minutes}m {seconds}s"
                else:
                    duration_str = f"{seconds}s"
            except:
                duration_str = "Unable to calculate"

        # Generate summary
        lines = []
        lines.append("📊 Session Complete")
        lines.append("=" * 60)
        lines.append(f"Session ID: {session_id}")
        lines.append(f"End Time: {datetime.now().isoformat()}")
        lines.append(f"End Reason: {reason}")
        lines.append("")

        lines.append("💬 Conversation Statistics:")
        lines.append(f"  • Total Conversation Turns: {conversation_turns}")
        lines.append(f"  • User Messages: {user_messages}")
        lines.append(f"  • Claude Responses: {claude_responses}")
        lines.append(f"  • Tool Observations: {tool_observations}")
        lines.append(f"  • System Messages: {system_messages}")
        lines.append(f"  • Total Messages: {len(pending_messages)}")
        lines.append("")

        lines.append("📚 Memory Statistics:")
        lines.append(f"  • Episodic Memories: {len(all_memories)}")
        lines.append(f"  • Pending Messages: {len(pending_messages)}")
        lines.append("")

        if first_time and last_time:
            lines.append("⏰ Session Duration:")
            lines.append(f"  • Started: {first_time}")
            lines.append(f"  • Ended: {last_time}")
            lines.append(f"  • Duration: {duration_str}")
            lines.append("")

        lines.append("✅ Session ended successfully")

        return "\n".join(lines)

    except Exception as e:
        # If summary generation fails, return a simple summary
        print(f"[WARNING] Failed to generate detailed summary: {e}", file=sys.stderr)
        return f"📊 Session Complete\n\nSession ID: {session_id}\nEnd Time: {datetime.now().isoformat()}\nEnd Reason: {reason}\n\n⚠️ Summary generation encountered an error, but session ended successfully."


def main():
    """Main execution"""
    try:
        # Read hook input
        hook_data = read_hook_input()

        session_id = hook_data.get('sessionId', 'unknown')
        cwd = hook_data.get('cwd', '')
        reason = hook_data.get('reason', 'other')

        # Debug: log received data
        print(f"[DEBUG] SessionEnd: sessionId={session_id}, cwd={cwd}, reason={reason}", file=sys.stderr)

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

        # Generate complete session summary
        print(f"[DEBUG] Generating complete session summary...", file=sys.stderr)
        summary = generate_session_summary(session_id, reason, client)

        print(f"[DEBUG] Storing session summary to EverMemOS...", file=sys.stderr)
        print(f"[DEBUG] Summary length: {len(summary)} chars", file=sys.stderr)

        # Store summary as user message with special sender name
        # Use role="user" because EverMemOS only includes user messages in pending_messages
        result = client.store_message(
            content=summary,
            role="user",
            sender_name="System (Session Complete)"
        )

        # Log success
        print(f"[DEBUG] Session summary stored successfully: {result.get('message', 'OK')}", file=sys.stderr)

        # Return success
        output = {"continue": True, "suppressOutput": True}
        print(json.dumps(output))
        sys.exit(0)

    except Exception as e:
        # Log error but don't block session end
        print(f"[ERROR] Failed to generate/store session summary: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)

        # Return success anyway (graceful failure)
        output = {"continue": True, "suppressOutput": True}
        print(json.dumps(output))
        sys.exit(0)


if __name__ == "__main__":
    main()
