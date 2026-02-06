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
from typing import Dict, List, Optional, Tuple


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

    def run_command(self, cmd: List[str], check: bool = True, capture: bool = True) -> Tuple[bool, str]:
        """Run shell command and return (success, output)"""
        try:
            if capture:
                result = subprocess.run(
                    cmd,
                    check=check,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                return result.returncode == 0, result.stdout
            else:
                result = subprocess.run(cmd, check=check, timeout=300)
                return result.returncode == 0, ""
        except subprocess.CalledProcessError as e:
            if check:
                self.print_error(f"Command failed: {' '.join(cmd)}")
                if hasattr(e, 'stderr') and e.stderr:
                    self.print_error(f"Error: {e.stderr}")
            return False, ""
        except subprocess.TimeoutExpired:
            self.print_error(f"Command timeout: {' '.join(cmd)}")
            return False, ""
        except FileNotFoundError:
            return False, ""

    def check_command_exists(self, cmd: str) -> bool:
        """Check if command exists"""
        success, _ = self.run_command(["which", cmd], check=False)
        return success

    def detect_setup_mode(self) -> str:
        """Detect appropriate setup mode based on system"""
        self.print_header("Detecting Setup Mode")

        # Check available resources
        has_docker = self.check_command_exists("docker")
        has_docker_compose = self.check_command_exists("docker-compose") or self.check_command_exists("docker")
        has_mongodb = self.check_command_exists("mongod")
        has_es = self.check_command_exists("elasticsearch")

        self.print_info(f"OS: {platform.system()} {platform.release()}")
        self.print_info(f"Docker: {'✅' if has_docker else '❌'}")
        self.print_info(f"Docker Compose: {'✅' if has_docker_compose else '❌'}")
        self.print_info(f"MongoDB: {'✅' if has_mongodb else '❌'}")
        self.print_info(f"Elasticsearch: {'✅' if has_es else '❌'}")

        # Recommend mode
        if has_docker and has_docker_compose:
            recommended = "standard"
            self.print_info("Recommended mode: standard (Docker-based)")
        elif has_mongodb and has_es:
            recommended = "full"
            self.print_info("Recommended mode: full (Native services)")
        else:
            recommended = "lite"
            self.print_info("Recommended mode: lite (Minimal dependencies)")

        return recommended

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
            # Download and run installer
            install_cmd = "curl -LsSf https://astral.sh/uv/install.sh | sh"
            result = subprocess.run(
                install_cmd,
                shell=True,
                check=True,
                capture_output=True,
                text=True
            )

            # Reload PATH
            uv_bin = Path.home() / ".cargo" / "bin"
            if uv_bin.exists():
                os.environ["PATH"] = f"{uv_bin}:{os.environ['PATH']}"

            self.print_success("uv installed successfully")
            return True
        except Exception as e:
            self.print_error(f"Failed to install uv: {e}")
            return False

    def install_docker(self) -> bool:
        """Install Docker based on operating system"""
        self.print_info("Installing Docker...")

        os_type = self.os_type

        try:
            if os_type == "linux":
                return self._install_docker_linux()
            elif os_type == "darwin":
                return self._install_docker_macos()
            else:
                self.print_error(f"Automatic Docker installation not supported on {os_type}")
                self.print_info("Please install Docker manually:")
                self.print_info("  https://docs.docker.com/get-docker/")
                return False
        except Exception as e:
            self.print_error(f"Failed to install Docker: {e}")
            return False

    def _install_docker_linux(self) -> bool:
        """Install Docker on Linux"""
        self.print_info("Detected Linux system, installing Docker...")

        try:
            # Detect Linux distribution
            distro = None
            if Path("/etc/os-release").exists():
                with open("/etc/os-release") as f:
                    content = f.read()
                    if "ubuntu" in content.lower() or "debian" in content.lower():
                        distro = "debian"
                    elif "centos" in content.lower() or "rhel" in content.lower() or "fedora" in content.lower():
                        distro = "rhel"

            if distro == "debian":
                self.print_info("Installing Docker on Debian/Ubuntu...")

                commands = [
                    # Update package index
                    "sudo apt-get update",
                    # Install prerequisites
                    "sudo apt-get install -y ca-certificates curl gnupg",
                    # Add Docker's official GPG key
                    "sudo install -m 0755 -d /etc/apt/keyrings",
                    "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg",
                    "sudo chmod a+r /etc/apt/keyrings/docker.gpg",
                    # Set up repository
                    'echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null',
                    # Update package index again
                    "sudo apt-get update",
                    # Install Docker
                    "sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin",
                ]

                for cmd in commands:
                    self.print_info(f"Running: {cmd}")
                    result = subprocess.run(
                        cmd,
                        shell=True,
                        check=True,
                        capture_output=True,
                        text=True
                    )

                # Start Docker service
                subprocess.run("sudo systemctl start docker", shell=True, check=True)
                subprocess.run("sudo systemctl enable docker", shell=True, check=True)

                # Add current user to docker group (optional, requires re-login)
                try:
                    username = os.environ.get("USER", os.environ.get("USERNAME"))
                    if username:
                        subprocess.run(f"sudo usermod -aG docker {username}", shell=True, check=True)
                        self.print_warning(f"Added {username} to docker group")
                        self.print_warning("You may need to log out and back in for group changes to take effect")
                except:
                    pass

                self.print_success("Docker installed successfully")
                return True

            elif distro == "rhel":
                self.print_info("Installing Docker on RHEL/CentOS/Fedora...")

                commands = [
                    "sudo yum install -y yum-utils",
                    "sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo",
                    "sudo yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin",
                    "sudo systemctl start docker",
                    "sudo systemctl enable docker",
                ]

                for cmd in commands:
                    self.print_info(f"Running: {cmd}")
                    subprocess.run(cmd, shell=True, check=True)

                self.print_success("Docker installed successfully")
                return True

            else:
                self.print_error("Could not detect Linux distribution")
                self.print_info("Please install Docker manually:")
                self.print_info("  https://docs.docker.com/engine/install/")
                return False

        except subprocess.CalledProcessError as e:
            self.print_error(f"Installation failed: {e}")
            self.print_info("\nTroubleshooting:")
            self.print_info("  1. Make sure you have sudo privileges")
            self.print_info("  2. Check your internet connection")
            self.print_info("  3. Try manual installation: https://docs.docker.com/engine/install/")
            return False

    def _install_docker_macos(self) -> bool:
        """Install Docker on macOS"""
        self.print_info("Detected macOS system")

        # Check if Homebrew is available
        if self.check_command_exists("brew"):
            self.print_info("Installing Docker Desktop via Homebrew...")

            try:
                # Install Docker Desktop
                subprocess.run(
                    ["brew", "install", "--cask", "docker"],
                    check=True,
                    capture_output=True,
                    text=True
                )

                self.print_success("Docker Desktop installed")
                self.print_warning("Please start Docker Desktop from Applications")
                self.print_info("After Docker Desktop starts, re-run this setup")
                return True

            except subprocess.CalledProcessError:
                self.print_error("Homebrew installation failed")

        # Fallback to manual instructions
        self.print_info("\nTo install Docker on macOS:")
        self.print_info("  1. Download Docker Desktop:")
        self.print_info("     https://docs.docker.com/desktop/install/mac-install/")
        self.print_info("  2. Open the downloaded .dmg file")
        self.print_info("  3. Drag Docker to Applications")
        self.print_info("  4. Launch Docker from Applications")
        self.print_info("  5. Wait for Docker to start")
        self.print_info("  6. Re-run this setup")
        return False

    def install_docker_compose(self) -> bool:
        """Install Docker Compose based on operating system"""
        self.print_info("Installing Docker Compose...")

        os_type = self.os_type

        try:
            if os_type == "linux":
                return self._install_docker_compose_linux()
            elif os_type == "darwin":
                return self._install_docker_compose_macos()
            else:
                self.print_error(f"Automatic Docker Compose installation not supported on {os_type}")
                self.print_info("Please install Docker Compose manually:")
                self.print_info("  https://docs.docker.com/compose/install/")
                return False
        except Exception as e:
            self.print_error(f"Failed to install Docker Compose: {e}")
            return False

    def _install_docker_compose_linux(self) -> bool:
        """Install Docker Compose on Linux"""
        self.print_info("Detected Linux system, installing Docker Compose...")

        try:
            # Detect Linux distribution
            distro = None
            if Path("/etc/os-release").exists():
                with open("/etc/os-release") as f:
                    content = f.read()
                    if "ubuntu" in content.lower() or "debian" in content.lower():
                        distro = "debian"
                    elif "centos" in content.lower() or "rhel" in content.lower() or "fedora" in content.lower():
                        distro = "rhel"

            if distro == "debian":
                self.print_info("Installing Docker Compose plugin on Debian/Ubuntu...")

                commands = [
                    "sudo apt-get update",
                    "sudo apt-get install -y docker-compose-plugin",
                ]

                for cmd in commands:
                    self.print_info(f"Running: {cmd}")
                    result = subprocess.run(
                        cmd,
                        shell=True,
                        check=True,
                        capture_output=True,
                        text=True
                    )

                self.print_success("Docker Compose plugin installed successfully")
                return True

            elif distro == "rhel":
                self.print_info("Installing Docker Compose plugin on RHEL/CentOS/Fedora...")

                commands = [
                    "sudo yum install -y docker-compose-plugin",
                ]

                for cmd in commands:
                    self.print_info(f"Running: {cmd}")
                    subprocess.run(cmd, shell=True, check=True)

                self.print_success("Docker Compose plugin installed successfully")
                return True

            else:
                self.print_error("Could not detect Linux distribution")
                self.print_info("Please install Docker Compose manually:")
                self.print_info("  https://docs.docker.com/compose/install/")
                return False

        except subprocess.CalledProcessError as e:
            self.print_error(f"Installation failed: {e}")
            self.print_info("\nTroubleshooting:")
            self.print_info("  1. Make sure you have sudo privileges")
            self.print_info("  2. Check your internet connection")
            self.print_info("  3. Verify Docker is installed first")
            self.print_info("  4. Try manual installation: https://docs.docker.com/compose/install/")
            return False

    def _install_docker_compose_macos(self) -> bool:
        """Install Docker Compose on macOS"""
        self.print_info("Detected macOS system")

        # Docker Desktop for macOS includes Docker Compose v2
        self.print_info("Docker Desktop for macOS includes Docker Compose v2")
        self.print_info("If Docker is installed but Compose isn't working:")
        self.print_info("  1. Make sure Docker Desktop is running")
        self.print_info("  2. Check Docker Desktop version is up to date")
        self.print_info("  3. Try restarting Docker Desktop")
        self.print_info("\nIf Docker Desktop is old, update it:")

        if self.check_command_exists("brew"):
            self.print_info("  brew upgrade --cask docker")
        else:
            self.print_info("  Download latest from: https://docs.docker.com/desktop/install/mac-install/")

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
# Minimal setup with no external services required

# Storage Mode
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

# Logging
LOG_LEVEL=INFO
LOG_FILE=data/evermemos.log
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

    def setup_standard_mode(self, non_interactive: bool = False) -> bool:
        """Setup standard mode (Docker-based)"""
        self.print_header("Setting Up Standard Mode (Docker)")
        self.print_info("Standard mode uses Docker containers for all services")

        # Check Docker
        if not self.check_command_exists("docker"):
            self.print_warning("Docker is not installed")

            if non_interactive:
                self.print_error("Docker is required for standard mode")
                self.print_info("Install Docker: https://docs.docker.com/get-docker/")
                return False

            # Ask user if they want to auto-install
            self.print_info("\nDocker is required for standard mode.")
            response = input("Would you like to install Docker automatically? (y/n): ").lower()

            if response == 'y':
                if self.install_docker():
                    self.print_success("Docker installed! Verifying...")

                    # Reload PATH and check again
                    import time
                    time.sleep(2)

                    if not self.check_command_exists("docker"):
                        self.print_warning("Docker installed but not yet available")
                        self.print_info("Please:")
                        if self.os_type == "darwin":
                            self.print_info("  1. Start Docker Desktop from Applications")
                            self.print_info("  2. Wait for Docker to fully start")
                        else:
                            self.print_info("  1. Log out and back in (for group permissions)")
                            self.print_info("  2. Or run: newgrp docker")
                        self.print_info("  3. Re-run this setup")
                        return False
                else:
                    self.print_error("Automatic installation failed")
                    self.print_info("Please install Docker manually:")
                    self.print_info("  https://docs.docker.com/get-docker/")
                    return False
            else:
                self.print_info("Please install Docker manually:")
                self.print_info("  https://docs.docker.com/get-docker/")
                return False

        # Check Docker Compose
        has_compose_v1 = self.check_command_exists("docker-compose")
        has_compose_v2, _ = self.run_command(["docker", "compose", "version"], check=False)

        if not (has_compose_v1 or has_compose_v2):
            self.print_warning("Docker Compose is not available")

            if non_interactive:
                self.print_error("Docker Compose is required for standard mode")
                self.print_info("Install Docker Compose: https://docs.docker.com/compose/install/")
                return False

            # Ask user if they want to auto-install
            self.print_info("\nDocker Compose is required for standard mode.")

            # On macOS, Docker Desktop should include Compose
            if self.os_type == "darwin":
                self.print_warning("Docker Compose should be included with Docker Desktop")
                self.print_info("Make sure Docker Desktop is running and up to date")
                response = input("Try to verify again? (y/n): ").lower()
                if response == 'y':
                    import time
                    time.sleep(2)
                    has_compose_v2, _ = self.run_command(["docker", "compose", "version"], check=False)
                    if has_compose_v2:
                        self.print_success("Docker Compose is now available!")
                    else:
                        self.print_error("Docker Compose still not available")
                        self.print_info("Please:")
                        self.print_info("  1. Update Docker Desktop to latest version")
                        if self.check_command_exists("brew"):
                            self.print_info("     brew upgrade --cask docker")
                        self.print_info("  2. Or download from: https://docs.docker.com/desktop/install/mac-install/")
                        return False
                else:
                    return False
            else:
                # Linux - offer to install
                response = input("Would you like to install Docker Compose automatically? (y/n): ").lower()

                if response == 'y':
                    if self.install_docker_compose():
                        self.print_success("Docker Compose installed! Verifying...")

                        # Reload PATH and check again
                        import time
                        time.sleep(2)

                        has_compose_v2, _ = self.run_command(["docker", "compose", "version"], check=False)
                        if not has_compose_v2:
                            self.print_warning("Docker Compose installed but not yet available")
                            self.print_info("Please try:")
                            self.print_info("  1. Restart your terminal")
                            self.print_info("  2. Or run: hash -r")
                            self.print_info("  3. Re-run this setup")
                            return False
                    else:
                        self.print_error("Automatic installation failed")
                        self.print_info("Please install Docker Compose manually:")
                        self.print_info("  https://docs.docker.com/compose/install/")
                        return False
                else:
                    self.print_info("Please install Docker Compose manually:")
                    self.print_info("  https://docs.docker.com/compose/install/")
                    return False

        # Create docker-compose.yml
        compose_file = self.project_dir / "docker-compose.yml"
        if not compose_file.exists():
            self.print_info("Creating docker-compose.yml...")

            compose_content = """version: '3.8'

services:
  mongodb:
    image: mongo:6.0
    container_name: evermemos-mongodb
    restart: unless-stopped
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db
    environment:
      MONGO_INITDB_ROOT_USERNAME: evermemos
      MONGO_INITDB_ROOT_PASSWORD: evermemos123
    networks:
      - evermemos-network

  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    container_name: evermemos-elasticsearch
    restart: unless-stopped
    ports:
      - "9200:9200"
      - "9300:9300"
    volumes:
      - es_data:/usr/share/elasticsearch/data
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    networks:
      - evermemos-network

  milvus-etcd:
    image: quay.io/coreos/etcd:v3.5.5
    container_name: evermemos-milvus-etcd
    restart: unless-stopped
    environment:
      - ETCD_AUTO_COMPACTION_MODE=revision
      - ETCD_AUTO_COMPACTION_RETENTION=1000
      - ETCD_QUOTA_BACKEND_BYTES=4294967296
      - ETCD_SNAPSHOT_COUNT=50000
    volumes:
      - etcd_data:/etcd
    command: etcd -advertise-client-urls=http://127.0.0.1:2379 -listen-client-urls=http://0.0.0.0:2379 --data-dir=/etcd
    networks:
      - evermemos-network

  milvus-minio:
    image: minio/minio:RELEASE.2023-03-20T20-16-18Z
    container_name: evermemos-milvus-minio
    restart: unless-stopped
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - minio_data:/minio_data
    command: minio server /minio_data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3
    networks:
      - evermemos-network

  milvus-standalone:
    image: milvusdb/milvus:v2.3.3
    container_name: evermemos-milvus
    restart: unless-stopped
    depends_on:
      - milvus-etcd
      - milvus-minio
    ports:
      - "19530:19530"
      - "9091:9091"
    volumes:
      - milvus_data:/var/lib/milvus
    environment:
      ETCD_ENDPOINTS: milvus-etcd:2379
      MINIO_ADDRESS: milvus-minio:9000
    command: ["milvus", "run", "standalone"]
    networks:
      - evermemos-network

volumes:
  mongodb_data:
  es_data:
  etcd_data:
  minio_data:
  milvus_data:

networks:
  evermemos-network:
    driver: bridge
"""
            compose_file.write_text(compose_content)
            self.print_success("Created docker-compose.yml")
        else:
            self.print_info("docker-compose.yml already exists")

        # Create .env.docker
        env_file = self.project_dir / ".env.docker"
        if not env_file.exists():
            self.print_info("Creating .env.docker configuration...")

            env_content = """# EverMemOS Standard (Docker) Configuration

# Storage Mode
STORAGE_MODE=standard
USE_MONGODB=true
USE_ELASTICSEARCH=true
USE_MILVUS=true

# MongoDB Configuration
MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_DATABASE=evermemos
MONGODB_USERNAME=evermemos
MONGODB_PASSWORD=evermemos123

# Elasticsearch Configuration
ELASTICSEARCH_HOST=localhost
ELASTICSEARCH_PORT=9200
ELASTICSEARCH_INDEX_PREFIX=evermemos

# Milvus Configuration
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_COLLECTION_PREFIX=evermemos

# Server Configuration
SERVER_HOST=0.0.0.0
SERVER_PORT=1995

# Memory Configuration
MEMORY_LIMIT=10000
ENABLE_VECTOR_SEARCH=true
VECTOR_DIMENSION=768

# Logging
LOG_LEVEL=INFO
LOG_FILE=data/evermemos.log
"""
            env_file.write_text(env_content)
            self.print_success("Created .env.docker")
        else:
            self.print_info(".env.docker already exists")

        # Create data directory
        data_dir = self.project_dir / "data"
        data_dir.mkdir(exist_ok=True)
        self.print_success("Created data directory")

        # Start Docker services
        self.print_info("\nStarting Docker services...")
        self.print_warning("This may take a few minutes on first run...")

        compose_cmd = ["docker-compose", "up", "-d"] if has_compose_v1 else ["docker", "compose", "up", "-d"]
        success, output = self.run_command(compose_cmd, check=False, capture=False)

        if success:
            self.print_success("Docker services started")
            self.print_info("Services running:")
            self.print_info("  - MongoDB: localhost:27017")
            self.print_info("  - Elasticsearch: localhost:9200")
            self.print_info("  - Milvus: localhost:19530")
        else:
            self.print_warning("Failed to start Docker services")
            self.print_info("You can start them manually later with:")
            self.print_info(f"  {' '.join(compose_cmd)}")

        return True

    def setup_full_mode(self) -> bool:
        """Setup full mode (Native services)"""
        self.print_header("Setting Up Full Mode (Native Services)")
        self.print_info("Full mode expects MongoDB, Elasticsearch, and Milvus already running")

        # Check for services
        has_mongodb = self.check_command_exists("mongod")
        has_es = self.check_command_exists("elasticsearch")

        if not has_mongodb:
            self.print_warning("MongoDB not detected")
            self.print_info("Install MongoDB: https://docs.mongodb.com/manual/installation/")

        if not has_es:
            self.print_warning("Elasticsearch not detected")
            self.print_info("Install Elasticsearch: https://www.elastic.co/guide/en/elasticsearch/reference/current/install-elasticsearch.html")

        # Create .env.production
        env_file = self.project_dir / ".env.production"
        if not env_file.exists():
            self.print_info("Creating .env.production configuration...")

            # Try to detect running services
            mongodb_host = "localhost"
            mongodb_port = 27017
            es_host = "localhost"
            es_port = 9200
            milvus_host = "localhost"
            milvus_port = 19530

            env_content = f"""# EverMemOS Full (Production) Configuration

# Storage Mode
STORAGE_MODE=full
USE_MONGODB=true
USE_ELASTICSEARCH=true
USE_MILVUS=true

# MongoDB Configuration
MONGODB_HOST={mongodb_host}
MONGODB_PORT={mongodb_port}
MONGODB_DATABASE=evermemos
MONGODB_USERNAME=
MONGODB_PASSWORD=

# Elasticsearch Configuration
ELASTICSEARCH_HOST={es_host}
ELASTICSEARCH_PORT={es_port}
ELASTICSEARCH_INDEX_PREFIX=evermemos

# Milvus Configuration
MILVUS_HOST={milvus_host}
MILVUS_PORT={milvus_port}
MILVUS_COLLECTION_PREFIX=evermemos

# Server Configuration
SERVER_HOST=0.0.0.0
SERVER_PORT=1995

# Memory Configuration
MEMORY_LIMIT=100000
ENABLE_VECTOR_SEARCH=true
VECTOR_DIMENSION=768

# Performance
WORKER_COUNT=4
MAX_CONNECTIONS=1000

# Logging
LOG_LEVEL=INFO
LOG_FILE=data/evermemos.log

# Security (IMPORTANT: Change these in production!)
SECRET_KEY=change-me-in-production
JWT_SECRET=change-me-in-production

# Monitoring
ENABLE_METRICS=true
METRICS_PORT=9090
"""
            env_file.write_text(env_content)
            self.print_success("Created .env.production")

            self.print_warning("\n⚠️  Important: Review and update .env.production:")
            self.print_info("  - Set MongoDB credentials if needed")
            self.print_info("  - Change SECRET_KEY and JWT_SECRET")
            self.print_info("  - Verify service endpoints")
        else:
            self.print_info(".env.production already exists")

        # Create data directory
        data_dir = self.project_dir / "data"
        data_dir.mkdir(exist_ok=True)
        self.print_success("Created data directory")

        # Verify services are accessible
        self.print_info("\nChecking service connectivity...")

        services_ok = True

        # Check MongoDB
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('localhost', 27017))
            sock.close()
            if result == 0:
                self.print_success("MongoDB is accessible")
            else:
                self.print_warning("MongoDB is not running (expected on localhost:27017)")
                services_ok = False
        except:
            self.print_warning("Could not check MongoDB")

        # Check Elasticsearch
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('localhost', 9200))
            sock.close()
            if result == 0:
                self.print_success("Elasticsearch is accessible")
            else:
                self.print_warning("Elasticsearch is not running (expected on localhost:9200)")
                services_ok = False
        except:
            self.print_warning("Could not check Elasticsearch")

        if not services_ok:
            self.print_info("\nTo start services:")
            if has_mongodb:
                self.print_info("  - MongoDB: sudo systemctl start mongod")
            if has_es:
                self.print_info("  - Elasticsearch: sudo systemctl start elasticsearch")
            self.print_info("  - Milvus: Follow https://milvus.io/docs/install_standalone-docker.md")

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

        success, _ = self.run_command(["uv", "sync"], capture=False)
        if success:
            self.print_success("Dependencies installed")
            return True
        else:
            self.print_error("Failed to install dependencies")
            return False

    def verify_installation(self) -> bool:
        """Verify installation"""
        self.print_header("Verifying Installation")

        # Determine config file based on mode
        if self.setup_mode == "lite":
            config_file = ".env.lite"
        elif self.setup_mode == "standard":
            config_file = ".env.docker"
        elif self.setup_mode == "full":
            config_file = ".env.production"
        else:
            config_file = ".env.lite"

        checks = [
            ("Project directory", self.project_dir.exists()),
            ("Source code", (self.project_dir / "src").exists()),
            (f"Configuration ({config_file})", (self.project_dir / config_file).exists()),
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

    def run_setup(self, mode: str = "auto", non_interactive: bool = False) -> bool:
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
            if non_interactive:
                self.print_error("uv is required for dependency management")
                return False

            self.print_info("uv is required for dependency management")
            response = input("Install uv now? (y/n): ").lower()
            if response == 'y':
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
        elif mode == "standard":
            if not self.setup_standard_mode(non_interactive=non_interactive):
                return False
        elif mode == "full":
            if not self.setup_full_mode():
                return False
        else:
            self.print_error(f"Unknown mode: {mode}")
            return False

        # Step 5: Verify
        if not self.verify_installation():
            return False

        # Success
        self.print_header("Setup Complete! 🎉")
        self.print_success("EverMemOS is ready to use")
        print()

        # Mode-specific instructions
        if mode == "lite":
            self.print_info("Lite mode setup complete - no external services needed")
        elif mode == "standard":
            self.print_info("Standard mode setup complete - Docker services started")
            self.print_info("Configuration file: .env.docker")
        elif mode == "full":
            self.print_info("Full mode setup complete - verify services are running")
            self.print_info("Configuration file: .env.production")
            self.print_warning("⚠️  Review .env.production and update credentials!")

        print()
        self.print_info("Next steps:")
        print("  1. Start the server:")
        print(f"     cd {self.project_dir}")

        if mode == "lite":
            print("     ENV_FILE=.env.lite uv run python src/run.py")
        elif mode == "standard":
            print("     ENV_FILE=.env.docker uv run python src/run.py")
        elif mode == "full":
            print("     ENV_FILE=.env.production uv run python src/run.py")

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
