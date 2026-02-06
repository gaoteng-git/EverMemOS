---
name: evermemos-start
description: Start, stop, restart, and manage EverMemOS service. Check status and view logs. Use when user wants to control EverMemOS service lifecycle.
argument-hint: "[start|stop|restart|status|logs]"
disable-model-invocation: false
allowed-tools: Bash(python3 *), Bash(tail *), Bash(curl *), Read
---

# EverMemOS Service Manager

Control EverMemOS service lifecycle with simple commands.

## Usage

```bash
/evermemos-start [action]
```

**Actions:**
- `start` (default) - Start the service
- `stop` - Stop the service
- `restart` - Restart the service
- `status` - Show service status
- `logs` - View service logs

## Automatic Usage

Claude will automatically use this skill when:

**User says:**
- "Start EverMemOS"
- "Is EverMemOS running?"
- "Show me the logs"
- "Stop the memory service"
- "Restart EverMemOS"

**Claude responds:**
```
I'll start EverMemOS for you.

[Runs: /evermemos-start]

🚀 Starting EverMemOS in background...
✅ EverMemOS started successfully (PID: 12345)
📝 Logs: /path/to/evermemos.log
🌐 API: http://localhost:1995

The service is now running!
```

## Commands

### Start Service

```bash
/evermemos-start
```

or

```bash
/evermemos-start start
```

**What it does:**
- Starts EverMemOS in background
- Saves process ID for management
- Verifies API is accessible
- Shows logs location

**Output:**
```
🚀 Starting EverMemOS in background...
✅ EverMemOS started successfully (PID: 12345)
📝 Logs: /path/to/data/evermemos.log
🌐 API: http://localhost:1995
```

---

### Stop Service

```bash
/evermemos-start stop
```

**What it does:**
- Gracefully stops EverMemOS
- Waits for clean shutdown
- Force kills if needed
- Cleans up PID file

**Output:**
```
⏹️  Stopping EverMemOS (PID: 12345)...
✅ EverMemOS stopped successfully
```

---

### Restart Service

```bash
/evermemos-start restart
```

**What it does:**
- Stops the service
- Waits briefly
- Starts it again

**Output:**
```
🔄 Restarting EverMemOS...
⏹️  Stopping EverMemOS (PID: 12345)...
✅ EverMemOS stopped successfully
🚀 Starting EverMemOS in background...
✅ EverMemOS started successfully (PID: 12346)
```

---

### Check Status

```bash
/evermemos-start status
```

**What it does:**
- Shows if service is running
- Displays PID
- Checks API accessibility
- Shows current mode

**Output:**
```
============================================================
                    EverMemOS Status
============================================================

🟢 Status: Running
🆔 PID: 12345
🌐 API: http://localhost:1995 ✅
⚙️  Mode: lite

📝 Logs: tail -f /path/to/data/evermemos.log
⏹️  Stop: /evermemos-start stop

============================================================
```

---

### View Logs

```bash
/evermemos-start logs
```

**What it does:**
- Shows last 50 lines of logs
- Useful for debugging

**Output:**
```
2026-02-04 10:30:15,123 - INFO - Starting EverMemOS server...
2026-02-04 10:30:15,456 - INFO - Loading configuration...
2026-02-04 10:30:16,789 - INFO - Server running on http://0.0.0.0:1995
...
```

## Usage Scenarios

### Scenario 1: First Time Start

```
User: Start EverMemOS

Claude: I'll start EverMemOS for you.

[Executes: python3 ~/.claude/skills/evermemos-start/scripts/service_manager.py start]

🚀 Starting EverMemOS in background...
✅ EverMemOS started successfully (PID: 12345)
📝 Logs: /path/to/evermemos.log
🌐 API: http://localhost:1995

EverMemOS is now running! You can:
- Check status: /evermemos-start status
- View logs: /evermemos-start logs
- Use memory features: /evermemos search "query"
```

---

### Scenario 2: Checking If Running

```
User: Is EverMemOS running?

Claude: Let me check the service status.

[Executes: python3 ~/.claude/skills/evermemos-start/scripts/service_manager.py status]

============================================================
                    EverMemOS Status
============================================================

🟢 Status: Running
🆔 PID: 12345
🌐 API: http://localhost:1995 ✅
⚙️  Mode: lite

Yes, EverMemOS is running and accessible!
```

---

### Scenario 3: Debugging Issues

```
User: Something is wrong with EverMemOS

Claude: Let me check the logs to see what's happening.

[Executes: python3 ~/.claude/skills/evermemos-start/scripts/service_manager.py logs]

2026-02-04 10:30:15 - ERROR - Connection refused: MongoDB
2026-02-04 10:30:16 - ERROR - Failed to initialize database

I see the issue - MongoDB is not running. Let me help fix this:

[Executes: /evermemos-doctor]

The diagnostic tool will help identify and resolve the issue.
```

---

### Scenario 4: Restart After Config Change

```
User: I just changed the configuration, how do I apply it?

Claude: I'll restart EverMemOS to apply your configuration changes.

[Executes: python3 ~/.claude/skills/evermemos-start/scripts/service_manager.py restart]

🔄 Restarting EverMemOS...
⏹️  Stopping EverMemOS...
✅ EverMemOS stopped
🚀 Starting EverMemOS...
✅ EverMemOS started (PID: 12346)

Configuration changes are now active!
```

---

## Background vs Foreground

### Background Mode (Default)
- Service runs in background
- Terminal is free to use
- Logs written to file
- Can close terminal safely

```bash
/evermemos-start
```

### Foreground Mode (Development)
- Service runs in terminal
- See logs in real-time
- Ctrl+C to stop
- Useful for debugging

```bash
python3 scripts/service_manager.py start --foreground
```

## File Locations

### PID File
`data/evermemos.pid` - Contains process ID

### Log File
`data/evermemos.log` - Service logs

### Configuration
`.env.lite` or `.env` - Environment configuration

## Integration with Other Skills

### After Setup
```
User: I just installed EverMemOS

Claude: Great! Now let's start the service.

[Executes: /evermemos-start]

✅ Service started successfully!
```

### Before Using Memory
```
User: /evermemos search "test"

Claude: Let me check if EverMemOS is running first...

[Executes: /evermemos-start status]

🔴 Service is not running. I'll start it for you.

[Executes: /evermemos-start]

✅ Service started. Now searching...

[Executes: /evermemos search "test"]
```

### Health Check
```
User: EverMemOS seems slow

Claude: Let me check the service status and logs.

[Executes: /evermemos-start status]
[Executes: /evermemos-start logs]

I see some performance warnings in the logs.
Let me run a full diagnostic:

[Executes: /evermemos-doctor]
```

## Troubleshooting

### Service Won't Start

**Check 1: Is it already running?**
```bash
/evermemos-start status
```

**Check 2: Are dependencies installed?**
```bash
/evermemos-doctor
```

**Check 3: Check the logs**
```bash
/evermemos-start logs
```

### Service Crashes Immediately

**View logs:**
```bash
tail -f /path/to/data/evermemos.log
```

Common issues:
- Port 1995 already in use
- Configuration error
- Missing dependencies

### Can't Stop Service

**Force stop:**
```bash
# Find PID
cat data/evermemos.pid

# Kill process
kill -9 <PID>

# Clean up PID file
rm data/evermemos.pid
```

## Advanced Options

### Custom Project Directory
```bash
python3 scripts/service_manager.py start --project-dir /path/to/evermemos
```

### Follow Logs in Real-time
```bash
python3 scripts/service_manager.py logs --follow
```

### Show More Log Lines
```bash
python3 scripts/service_manager.py logs --lines 100
```

## Success Indicators

Service is healthy when:

✅ Status shows "Running"
✅ API is accessible (http://localhost:1995)
✅ No errors in recent logs
✅ Can perform memory operations

## Error Messages

### "Port 1995 already in use"
```
Solution:
1. Check if another instance is running
2. Stop it: /evermemos-start stop
3. Or change port in .env file
```

### "Permission denied"
```
Solution:
1. Check file permissions
2. Ensure data directory is writable
3. Run with appropriate permissions
```

### "Configuration error"
```
Solution:
1. Check .env file exists
2. Verify configuration syntax
3. Run: /evermemos-config to reconfigure
```

## Best Practices

### Daily Usage
1. Start once at beginning of day: `/evermemos-start`
2. Use throughout the day: `/evermemos ...`
3. Check status if issues: `/evermemos-start status`
4. Stop before shutdown (optional)

### Development
1. Run in foreground for debugging
2. Watch logs in real-time
3. Restart after code changes

### Production
1. Start in background
2. Monitor logs regularly
3. Set up auto-restart on crash
4. Use health checks

---

## Quick Reference

| Task | Command |
|------|---------|
| Start service | `/evermemos-start` |
| Stop service | `/evermemos-start stop` |
| Restart service | `/evermemos-start restart` |
| Check status | `/evermemos-start status` |
| View logs | `/evermemos-start logs` |
| Is it running? | `/evermemos-start status` |

---

For more help:
- Setup: `/evermemos-setup`
- Configuration: `/evermemos-config`
- Health check: `/evermemos-doctor`
