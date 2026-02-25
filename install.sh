#!/bin/bash
# EverMemOS One-Command Installer
#
# Usage:
#   ./install.sh              # interactive (recommended for first time)
#   ./install.sh --non-interactive  # fully automated (CI / headless)
#
# What this does:
#   1. Installs uv + Python dependencies
#   2. Starts Docker services (MongoDB, Elasticsearch, Milvus, Redis)
#   3. Copies EverMemOS skills to ~/.claude/skills/
#   4. Merges hooks into ~/.claude/settings.json (global, all projects)
#   5. Starts the EverMemOS backend server

set -e

# ── Resolve project root (works when called from any directory) ──────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "============================================================"
echo "           EverMemOS Installer"
echo "============================================================"
echo ""

# ── Check Python 3 ──────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "❌ python3 not found. Please install Python 3.8+ and retry."
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✅ Python $PYTHON_VERSION"

# ── Step 1-6: Setup (deps, Docker, skills, global hooks) ────────────────────
echo ""
echo "▶  Running setup..."
echo ""
python3 claude-skills/evermemos-setup/scripts/setup.py "$@"

# ── Step 7: Start EverMemOS backend ─────────────────────────────────────────
echo ""
echo "▶  Starting EverMemOS backend..."
echo ""
python3 claude-skills/evermemos-start/scripts/service_manager.py start

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  ✅ EverMemOS is ready!"
echo ""
echo "  API:  http://localhost:8001"
echo "  Logs: data/evermemos.log"
echo ""
echo "  ⚠️  If Claude Code is already running, restart it so the"
echo "     newly added hooks take effect in all projects."
echo "============================================================"
echo ""
