#!/bin/bash
# View EverMemOS hook logs

LOG_DIR="$HOME/.claude/logs"

# Available log files
HOOK_LOGS=(
    "hook_user_prompt"
    "hook_session_start"
    "hook_stop"
    "hook_tool_use"
    "hook_session_end"
    "evermemos_hooks"
)

show_help() {
    cat << 'HELP'
📚 EverMemOS Log Viewer

Usage:
  view_logs.sh [hook_name] [options] [number]

Hook Names:
  user        hook_user_prompt.log      - User message submissions
  session     hook_session_start.log    - Session start events
  stop        hook_stop.log             - Stop events
  tool        hook_tool_use.log         - Tool usage events
  end         hook_session_end.log      - Session end events
  all         (default) Show all logs combined

Options:
  -f, --follow     Follow log file in real-time (like tail -f)
  -c, --clear      Clear the log file(s)
  -l, --list       List all available log files
  -h, --help       Show this help message
  [number]         Show last N lines (default: 50)

Examples:
  view_logs.sh                 # Show last 50 lines from all logs
  view_logs.sh tool            # Show last 50 lines from hook_tool_use.log
  view_logs.sh user 100        # Show last 100 lines from hook_user_prompt.log
  view_logs.sh tool -f         # Follow tool usage logs in real-time
  view_logs.sh -c              # Clear all logs
  view_logs.sh user -c         # Clear only user prompt logs
  view_logs.sh -l              # List all log files

Log directory: ~/.claude/logs/
HELP
}

list_logs() {
    echo "📁 Available log files in $LOG_DIR:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    for log_name in "${HOOK_LOGS[@]}"; do
        log_file="$LOG_DIR/${log_name}.log"
        if [ -f "$log_file" ]; then
            size=$(du -h "$log_file" | cut -f1)
            lines=$(wc -l < "$log_file")
            echo "✅ ${log_name}.log ($size, $lines lines)"
        else
            echo "❌ ${log_name}.log (not created yet)"
        fi
    done
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

get_log_file() {
    local hook_name="$1"

    case "$hook_name" in
        user)       echo "$LOG_DIR/hook_user_prompt.log" ;;
        session)    echo "$LOG_DIR/hook_session_start.log" ;;
        stop)       echo "$LOG_DIR/hook_stop.log" ;;
        tool)       echo "$LOG_DIR/hook_tool_use.log" ;;
        end)        echo "$LOG_DIR/hook_session_end.log" ;;
        all|"")     echo "ALL" ;;
        *)          echo "$LOG_DIR/${hook_name}.log" ;;
    esac
}

clear_logs() {
    local target="$1"

    if [ "$target" = "ALL" ] || [ -z "$target" ]; then
        echo "🗑️  Clearing all log files..."
        for log_name in "${HOOK_LOGS[@]}"; do
            log_file="$LOG_DIR/${log_name}.log"
            if [ -f "$log_file" ]; then
                > "$log_file"
                echo "  ✅ Cleared ${log_name}.log"
            fi
        done
        echo "✅ All log files cleared"
    else
        if [ -f "$target" ]; then
            > "$target"
            echo "✅ Log file cleared: $target"
        else
            echo "❌ Log file not found: $target"
            exit 1
        fi
    fi
}

show_logs() {
    local target="$1"
    local lines="${2:-50}"

    if [ "$target" = "ALL" ]; then
        echo "📝 Last $lines log entries from all hooks:"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

        # Combine all logs and sort by timestamp
        for log_name in "${HOOK_LOGS[@]}"; do
            log_file="$LOG_DIR/${log_name}.log"
            if [ -f "$log_file" ] && [ -s "$log_file" ]; then
                # Add hook name prefix to each line
                while IFS= read -r line; do
                    echo "[$log_name] $line"
                done < "$log_file"
            fi
        done | sort -t']' -k1 | tail -n "$lines"

        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "💡 Use 'view_logs.sh -h' for more options"
    else
        if [ ! -f "$target" ]; then
            echo "❌ Log file not found: $target"
            echo "💡 Use 'view_logs.sh -l' to list available logs"
            exit 1
        fi

        if [ ! -s "$target" ]; then
            echo "📭 Log file is empty: $target"
            exit 0
        fi

        echo "📝 Last $lines log entries from $(basename "$target"):"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        tail -n "$lines" "$target"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "📍 Log file: $target"
        echo "💡 Use 'view_logs.sh -h' for more options"
    fi
}

follow_logs() {
    local target="$1"

    if [ "$target" = "ALL" ]; then
        echo "📡 Following all log files (Ctrl+C to stop)..."
        # Use tail -f on all existing log files
        local files=()
        for log_name in "${HOOK_LOGS[@]}"; do
            log_file="$LOG_DIR/${log_name}.log"
            if [ -f "$log_file" ]; then
                files+=("$log_file")
            fi
        done

        if [ ${#files[@]} -eq 0 ]; then
            echo "❌ No log files found"
            exit 1
        fi

        tail -f "${files[@]}"
    else
        if [ ! -f "$target" ]; then
            echo "❌ Log file not found: $target"
            exit 1
        fi

        echo "📡 Following $(basename "$target") (Ctrl+C to stop)..."
        tail -f "$target"
    fi
}

# Main logic
HOOK_NAME=""
ACTION="show"
LINES=50

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            show_help
            exit 0
            ;;
        -l|--list)
            list_logs
            exit 0
            ;;
        -c|--clear)
            ACTION="clear"
            shift
            ;;
        -f|--follow)
            ACTION="follow"
            shift
            ;;
        -a|--all)
            HOOK_NAME="all"
            shift
            ;;
        user|session|stop|tool|end|all)
            HOOK_NAME="$1"
            shift
            ;;
        [0-9]*)
            LINES="$1"
            shift
            ;;
        *)
            # Assume it's a custom log name
            HOOK_NAME="$1"
            shift
            ;;
    esac
done

# Get target log file
LOG_FILE=$(get_log_file "$HOOK_NAME")

# Execute action
case "$ACTION" in
    clear)
        clear_logs "$LOG_FILE"
        ;;
    follow)
        follow_logs "$LOG_FILE"
        ;;
    show)
        show_logs "$LOG_FILE" "$LINES"
        ;;
esac
