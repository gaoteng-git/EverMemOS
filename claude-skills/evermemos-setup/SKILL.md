---
name: evermemos-setup
description: Install and configure EverMemOS with automated setup wizard. Use when user wants to install EverMemOS or needs help with initial setup.
argument-hint: "[mode]"
disable-model-invocation: false
allowed-tools: Bash(python3 *), Bash(uv *), Bash(curl *), Read, Write
---

# EverMemOS Setup Wizard

Automated installation and configuration for EverMemOS. This skill guides users through the setup process without requiring deep technical knowledge.

## Usage

```bash
/evermemos-setup [mode]
```

**Parameters:**
- `mode` (optional): Setup mode - `auto` (default), `lite`, `standard`, or `full`

## Setup Modes

### 🚀 Lite Mode (Recommended for beginners)
- **No external services required**
- Uses SQLite for storage
- In-memory vector search
- Perfect for testing and development
- Quick setup (< 2 minutes)

### 🔧 Standard Mode (Docker-based)
- Uses Docker containers
- MongoDB + Elasticsearch + Milvus
- Good balance of features and ease
- Requires Docker installed

### ⚡ Full Mode (Production-ready)
- Native service installation
- Full performance optimization
- Requires manual service management
- Best for production deployment

## What This Skill Does

### 1. System Check
- Detect operating system
- Check Python version (3.8+ required)
- Check for existing installations
- Recommend appropriate setup mode

### 2. Install Dependencies
- Install `uv` package manager (if needed)
- Install Python dependencies
- Set up project structure

### 3. Configuration
- Create appropriate `.env` file
- Set up data directories
- Configure based on selected mode

### 4. Verification
- Verify all components installed
- Run health checks
- Provide next steps

## Automatic Usage

Claude will automatically suggest this skill when:

**User says:**
- "How do I install EverMemOS?"
- "Help me set up EverMemOS"
- "I want to use EverMemOS but don't know how to install it"
- "EverMemOS installation guide"

**Claude responds:**
```
I'll help you install EverMemOS with the automated setup wizard.

[Runs: /evermemos-setup auto]

The wizard will:
1. Check your system
2. Recommend the best setup mode
3. Install all dependencies
4. Configure everything automatically

Let me start the setup process...
```

## Manual Usage Examples

### Example 1: Auto-detect Best Mode

```bash
/evermemos-setup
```

or

```bash
/evermemos-setup auto
```

The wizard will detect your system and recommend the best mode.

### Example 2: Lite Mode (Quick Start)

```bash
/evermemos-setup lite
```

Fastest way to get started - no external services needed.

### Example 3: Docker-based Setup

```bash
/evermemos-setup standard
```

Uses Docker containers for all services.

## Step-by-Step Process

### When User Asks for Installation

**User:** "How do I install EverMemOS?"

**Claude automatically:**

1. **Assess User's Technical Level**
   - Ask about their experience if unclear
   - Recommend appropriate mode

2. **Run Setup Wizard**
   ```bash
   python3 ~/.claude/skills/evermemos-setup/scripts/setup.py --mode auto
   ```

3. **Guide Through Process**
   - Explain each step
   - Handle any errors
   - Provide troubleshooting help

4. **Verify Success**
   - Confirm installation complete
   - Show how to start the server
   - Suggest next steps

### Handling Different User Levels

#### Beginner User
```
User: I want to try EverMemOS but I'm not very technical

Claude: No problem! I'll set up EverMemOS in lite mode -
it's the easiest way and requires no additional software.

[Runs: /evermemos-setup lite]

This will:
✅ Install everything you need
✅ No database setup required
✅ Ready to use in 2 minutes
```

#### Experienced User
```
User: I need EverMemOS for production with full capabilities

Claude: I'll set up the full production environment with
MongoDB, Elasticsearch, and Milvus.

[Runs: /evermemos-setup full]

This will install and configure:
- MongoDB for primary storage
- Elasticsearch for full-text search
- Milvus for vector similarity
```

## Error Handling

The skill handles common issues:

### Python Version Too Old
```
❌ Python 3.8+ required, found 3.7

Solution: Please upgrade Python first:
- Ubuntu: sudo apt install python3.11
- macOS: brew install python@3.11
```

### Missing Dependencies
```
⚠️  uv not found

Installing uv package manager...
✅ uv installed successfully
```

### Insufficient Permissions
```
❌ Cannot create directory: Permission denied

Solution: Run with appropriate permissions or
choose a different installation directory
```

## Configuration Files Created

### Lite Mode: `.env.lite`
```bash
STORAGE_MODE=lite
USE_MONGODB=false
USE_ELASTICSEARCH=false
USE_MILVUS=false
SQLITE_DB_PATH=data/evermemos.db
SERVER_PORT=1995
```

### Standard Mode: `.env.docker`
```bash
STORAGE_MODE=standard
MONGODB_URL=mongodb://localhost:27017
ELASTICSEARCH_URL=http://localhost:9200
MILVUS_HOST=localhost
MILVUS_PORT=19530
```

### Full Mode: `.env.production`
```bash
STORAGE_MODE=full
# All services with production settings
```

## Post-Installation

After setup completes, guide user to:

1. **Start the server:**
   ```bash
   /evermemos-start
   ```
   or
   ```bash
   cd /path/to/EverMemOS
   uv run python src/run.py
   ```

2. **Verify it's running:**
   ```bash
   curl http://localhost:1995
   ```

3. **Install the memory skill:**
   ```bash
   /evermemos-setup-skill
   ```

## Troubleshooting

If setup fails, run diagnostics:

```bash
/evermemos-doctor
```

This will identify issues and suggest fixes.

## Advanced Options

### Custom Project Directory

```bash
/evermemos-setup --project-dir /custom/path
```

### Non-Interactive Mode

```bash
/evermemos-setup --mode lite --non-interactive
```

## Integration with Other Skills

This skill works with:

- **`/evermemos-start`** - Start/stop services
- **`/evermemos-config`** - Modify configuration
- **`/evermemos-doctor`** - Health checks and diagnostics
- **`/evermemos`** - Main memory skill (install after setup)

## Requirements

### Minimum
- Python 3.8+
- 1GB RAM
- 500MB disk space

### Recommended
- Python 3.10+
- 4GB RAM
- 2GB disk space

### For Full Mode
- MongoDB 4.4+
- Elasticsearch 7.10+
- Milvus 2.0+

## Success Indicators

Setup is successful when:

✅ All dependencies installed
✅ Configuration file created
✅ Data directories set up
✅ Server can start without errors
✅ Health check passes

## Next Steps After Setup

Guide user to:

1. Start the server: `/evermemos-start`
2. Test the API: `curl http://localhost:1995`
3. Install memory skill: `cp -r claude-skills/evermemos ~/.claude/skills/`
4. Try it out: `/evermemos store "Test message" user`

---

## Implementation Notes

The setup script (`scripts/setup.py`) provides:

- **System detection** - Auto-detect OS and available resources
- **Dependency management** - Install required packages
- **Configuration generation** - Create appropriate config files
- **Verification** - Ensure everything works
- **User-friendly output** - Colored, formatted messages
- **Error recovery** - Handle common issues automatically

---

## Example Session

```
User: I want to use EverMemOS but have no idea how to install it

Claude: I'll help you get EverMemOS up and running! Since you're
new to this, I recommend lite mode - it's the simplest setup with
no external dependencies.

[Executes: /evermemos-setup lite]

Starting EverMemOS Setup Wizard...

============================================================
                  Detecting Setup Mode
============================================================

ℹ️  OS: Linux 5.15.0
ℹ️  Docker: ❌
ℹ️  MongoDB: ❌
ℹ️  Elasticsearch: ❌
ℹ️  Recommended mode: lite (Minimal dependencies)

============================================================
                Installing Dependencies
============================================================

ℹ️  Checking Python version...
✅ Python 3.11.5

ℹ️  Checking uv package manager...
✅ uv is installed

ℹ️  Installing Python packages with uv...
✅ Dependencies installed

============================================================
                  Setting Up Lite Mode
============================================================

ℹ️  Lite mode uses SQLite and in-memory storage
ℹ️  Creating .env.lite configuration...
✅ Created .env.lite
✅ Created data directory

============================================================
                 Verifying Installation
============================================================

✅ Project directory: OK
✅ Source code: OK
✅ Configuration: OK
✅ Data directory: OK

============================================================
                 Setup Complete! 🎉
============================================================

✅ EverMemOS is ready to use

ℹ️  Next steps:
  1. Start the server:
     cd /home/op/gaoteng/git/EverMemOS
     uv run python src/run.py

  2. Or use the skill:
     /evermemos-start

That's it! EverMemOS is now installed and configured.
Would you like me to start the server for you?
```

---

For detailed documentation, see:
- Setup troubleshooting guide
- Configuration reference
- Advanced installation options
