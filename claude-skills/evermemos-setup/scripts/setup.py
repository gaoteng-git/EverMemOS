#!/usr/bin/env python3
"""
EverMemOS Setup Script

Automated installation and initialization for EverMemOS.
"""

import os
import sys
import subprocess
import platform
import json
from pathlib import Path
from typing import Dict, List, Optional


class Colors:
    """Terminal colors"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


class SetupManager:
    """Manages EverMemOS setup process"""

    def __init__(self, project_dir: Optional[str] = None):
        self.project_dir = Path(project_dir) if project_dir else Path.cwd()
        self.os_type = platform.system().lower()
        self.setup_mode = "lite"  # lite, standard, full

    def print_header(self, text: str):
        """Print formatted header"""
        print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{text:^60}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")

    def print_success(self, text: str):
        """Print success message"""
        print(f"{Colors.OKGREEN}✅ {text}{Colors.ENDC}")

    def print_warning(self, text: str):
        """Print warning message"""
        print(f"{Colors.WARNING}⚠️  {text}{Colors.ENDC}")

    def print_error(self, text: str):
        """Print error message"""
        print(f"{Colors.FAIL}❌ {text}{Colors.ENDC}")

    def print_info(self, text: str):
        """Print info message"""
        print(f"{Colors.OKCYAN}ℹ️  {text}{Colors.ENDC}")

    def run_command(self, cmd: List[str], check: bool = True) -> bool:
        """Run shell command and return success status"""
        try:
            result = subprocess.run(
                cmd,
                check=check,
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except subprocess.CalledProcessError as e:
            if check:
                self.print_error(f"Command failed: {' '.join(cmd)}")
                self.print_error(f"Error: {e.stderr}")
            return False
        except FileNotFoundError:
            return False

    def check_command_exists(self, cmd: str) -> bool:
        """Check if command exists"""
        return self.run_command(["which", cmd], check=False)

    def detect_setup_mode(self) -> str:
        """Detect appropriate setup mode based on system"""
        self.print_header("Detecting Setup Mode")

        # Check available resources
        has_docker = self.check_command_exists("docker")
        has_mongodb = self.check_command_exists("mongod")
        has_es = self.check_command_exists("elasticsearch")

        self.print_info(f"OS: {platform.system()} {platform.release()}")
        self.print_info(f"Docker: {'✅' if has_docker else '❌'}")
        self.print_info(f"MongoDB: {'✅' if has_mongodb else '❌'}")
        self.print_info(f"Elasticsearch: {'✅' if has_es else '❌'}")

        # Recommend mode
        if has_docker:
            recommended = "standard (Docker-based)"
        elif has_mongodb and has_es:
            recommended = "full (Native services)"
        else:
            recommended = "lite (Minimal dependencies)"

        self.print_info(f"Recommended mode: {recommended}")
        return recommended.split()[0]

    def check_python(self) -> bool:
        """Check Python version"""
        self.print_info("Checking Python version...")
        version = sys.version_info

        if version.major < 3 or (version.major == 3 and version.minor < 8):
            self.print_error(f"Python 3.8+ required, found {version.major}.{version.minor}")
            return False

        self.print_success(f"Python {version.major}.{version.minor}.{version.micro}")
        return True

    def check_uv(self) -> bool:
        """Check if uv is installed"""
        self.print_info("Checking uv package manager...")

        if self.check_command_exists("uv"):
            self.print_success("uv is installed")
            return True

        self.print_warning("uv not found")
        return False

    def install_uv(self) -> bool:
        """Install uv package manager"""
        self.print_info("Installing uv...")

        try:
            subprocess.run(
                ["curl", "-LsSf", "https://astral.sh/uv/install.sh"],
                stdout=subprocess.PIPE,
                check=True
            )
            result = subprocess.run(
                ["sh"],
                input=subprocess.run(
                    ["curl", "-LsSf", "https://astral.sh/uv/install.sh"],
                    capture_output=True,
                    check=True
                ).stdout,
                check=True
            )

            self.print_success("uv installed successfully")
            return True
        except Exception as e:
            self.print_error(f"Failed to install uv: {e}")
            return False

    def setup_lite_mode(self) -> bool:
        """Setup lite mode (SQLite + DuckDB)"""
        self.print_header("Setting Up Lite Mode")
        self.print_info("Lite mode uses SQLite and in-memory storage - no external services needed")

        # Create .env.lite if not exists
        env_file = self.project_dir / ".env.lite"
        if not env_file.exists():
            self.print_info("Creating .env.lite configuration...")

            env_content = """# EverMemOS Lite Configuration
STORAGE_MODE=lite
USE_MONGODB=false
USE_ELASTICSEARCH=false
USE_MILVUS=false

# SQLite Database
SQLITE_DB_PATH=data/evermemos.db

# DuckDB for analytics
DUCKDB_PATH=data/evermemos_analytics.duckdb

# Server Configuration
SERVER_HOST=0.0.0.0
SERVER_PORT=1995

# Memory Configuration
MEMORY_LIMIT=1000
ENABLE_VECTOR_SEARCH=false
"""
            env_file.write_text(env_content)
            self.print_success("Created .env.lite")
        else:
            self.print_info(".env.lite already exists")

        # Create data directory
        data_dir = self.project_dir / "data"
        data_dir.mkdir(exist_ok=True)
        self.print_success("Created data directory")

        return True

    def install_dependencies(self) -> bool:
        """Install Python dependencies"""
        self.print_header("Installing Dependencies")

        # Check if pyproject.toml exists
        if not (self.project_dir / "pyproject.toml").exists():
            self.print_error("pyproject.toml not found")
            return False

        # Install with uv
        self.print_info("Installing Python packages with uv...")
        os.chdir(self.project_dir)

        if self.run_command(["uv", "sync"]):
            self.print_success("Dependencies installed")
            return True
        else:
            self.print_error("Failed to install dependencies")
            return False

    def verify_installation(self) -> bool:
        """Verify installation"""
        self.print_header("Verifying Installation")

        checks = [
            ("Project directory", self.project_dir.exists()),
            ("Source code", (self.project_dir / "src").exists()),
            ("Configuration", (self.project_dir / ".env.lite").exists()),
            ("Data directory", (self.project_dir / "data").exists()),
        ]

        all_good = True
        for check_name, result in checks:
            if result:
                self.print_success(f"{check_name}: OK")
            else:
                self.print_error(f"{check_name}: Failed")
                all_good = False

        return all_good

    def run_setup(self, mode: str = "auto") -> bool:
        """Run complete setup process"""
        self.print_header("EverMemOS Setup Wizard")

        # Detect mode if auto
        if mode == "auto":
            mode = self.detect_setup_mode()

        self.setup_mode = mode
        self.print_info(f"Setup mode: {mode}")

        # Step 1: Check Python
        if not self.check_python():
            return False

        # Step 2: Check/Install uv
        if not self.check_uv():
            self.print_info("uv is required for dependency management")
            if input("Install uv now? (y/n): ").lower() == 'y':
                if not self.install_uv():
                    return False
            else:
                self.print_error("uv is required to continue")
                return False

        # Step 3: Install dependencies
        if not self.install_dependencies():
            return False

        # Step 4: Setup based on mode
        if mode == "lite":
            if not self.setup_lite_mode():
                return False
        else:
            self.print_warning(f"Mode '{mode}' not yet implemented, using lite mode")
            if not self.setup_lite_mode():
                return False

        # Step 5: Verify
        if not self.verify_installation():
            return False

        # Success
        self.print_header("Setup Complete! 🎉")
        self.print_success("EverMemOS is ready to use")
        print()
        self.print_info("Next steps:")
        print("  1. Start the server:")
        print(f"     cd {self.project_dir}")
        print("     uv run python src/run.py")
        print()
        print("  2. Or use the skill:")
        print("     /evermemos-start")
        print()

        return True


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="EverMemOS Setup Wizard"
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "lite", "standard", "full"],
        default="auto",
        help="Setup mode (default: auto-detect)"
    )
    parser.add_argument(
        "--project-dir",
        type=str,
        default=None,
        help="Project directory (default: current directory)"
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run in non-interactive mode"
    )

    args = parser.parse_args()

    # Create setup manager
    manager = SetupManager(project_dir=args.project_dir)

    # Run setup
    success = manager.run_setup(mode=args.mode)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
