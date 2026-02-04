---
name: evermemos-setup
description: Install and configure EverMemOS with Docker containers for MongoDB, Elasticsearch, and Milvus. Automated setup with Docker auto-installation.
disable-model-invocation: false
allowed-tools: Bash(python3 *), Bash(uv *), Bash(curl *), Bash(docker *), Read, Write
---

# EverMemOS Setup Wizard

Automated installation and configuration for EverMemOS using Docker containers. This skill sets up MongoDB, Elasticsearch, and Milvus in Docker, with automatic Docker installation if needed.

## Usage

```bash
/evermemos-setup
```

No parameters needed - the setup wizard handles everything automatically.

## What Gets Installed

### Docker Services
- **MongoDB 7.0** - Primary database
- **Elasticsearch 8.11.0** - Full-text search
- **Milvus 2.5.2** - Vector database for semantic search
- **Redis 7.2** - Cache and KV storage
- **Supporting services** - etcd, MinIO (for Milvus)

### Auto-Installation
- **Docker** - Automatically installs if not present (Linux & macOS)
- **Docker Compose** - Automatically installs if not present
- **uv package manager** - Python dependency management
- **EverMemOS dependencies** - All Python packages

## What This Skill Does

### 1. System Check
- Detect operating system (Linux, macOS)
- Check Python version (3.8+ required)
- Check for existing installations
- Verify system resources

### 2. Install Docker (if needed)
- **Linux (Debian/Ubuntu)**: Installs Docker CE via apt
- **Linux (RHEL/CentOS/Fedora)**: Installs Docker CE via yum
- **macOS**: Installs Docker Desktop via Homebrew
- Asks user permission before installing
- Shows progress during installation

### 3. Install Docker Compose (if needed)
- **Linux**: Installs docker-compose-plugin
- **macOS**: Verifies Docker Desktop includes Compose
- Consistent user experience with Docker installation

### 4. Install Dependencies
- Install `uv` package manager automatically
- Install Python dependencies via uv
- Set up project structure

### 5. Create Docker Services
- Generate `docker-compose.yml` with all services
- Configure MongoDB with authentication
- Configure Elasticsearch for development
- Configure Milvus with dependencies
- Set up Docker networks and volumes

### 6. Configuration
- Create `.env.docker` configuration file
- Set up data directories
- Configure service connection strings
- Set optimal defaults for Docker environment

### 7. Start Services
- Start all Docker containers automatically
- Verify services are running
- Test connectivity

### 8. Verification
- Check all containers are healthy
- Verify MongoDB connection
- Verify Elasticsearch connection
- Verify Milvus connection
- Provide service URLs and next steps

## Automatic Usage

Claude will automatically suggest this skill when:

**User says:**
- "How do I install EverMemOS?"
- "Help me set up EverMemOS"
- "I want to use EverMemOS but don't know how to install it"
- "Install EverMemOS for me"
- "Set up EverMemOS with Docker"

**Claude responds:**
```
I'll help you install EverMemOS with Docker containers.

[Runs: /evermemos-setup]

The setup wizard will:
1. Check your system
2. Install Docker if needed (asks permission first)
3. Install Docker Compose if needed
4. Set up MongoDB, Elasticsearch, and Milvus in Docker
5. Configure everything automatically
6. Start all services

Let me start the setup process...
```

## Manual Usage

### Basic Setup

```bash
/evermemos-setup
```

This will:
- Check if Docker is installed (auto-install if user agrees)
- Check if Docker Compose is installed (auto-install if user agrees)
- Create docker-compose.yml
- Create .env.docker configuration
- Start all Docker services
- Verify everything is working

### Expected Output

```
============================================================
                    EVERMEMOS SETUP
============================================================

Detecting system...
✅ Operating System: Linux (Ubuntu)
✅ Python 3.10.12

Checking Docker...
⚠️  Docker is not installed
ℹ️  Docker is required to run EverMemOS services.
Would you like to install Docker automatically? (y/n): y

🔄 Installing Docker...
ℹ️  Installing Docker on Debian/Ubuntu...
ℹ️  Running: sudo apt-get update
ℹ️  Running: sudo apt-get install -y docker-ce docker-ce-cli containerd.io
✅ Docker installed successfully!

Checking Docker Compose...
⚠️  Docker Compose is not available
Would you like to install Docker Compose automatically? (y/n): y

🔄 Installing Docker Compose...
✅ Docker Compose installed successfully!

Creating docker-compose.yml...
✅ Docker Compose configuration created

Creating .env.docker configuration...
✅ Configuration file created

Starting Docker services...
ℹ️  Starting MongoDB, Elasticsearch, and Milvus...
✅ All services started successfully

Verifying services...
✅ MongoDB is running on port 27017
✅ Elasticsearch is running on port 9200
✅ Milvus is running on port 19530

============================================================
                    SETUP COMPLETE!
============================================================

✅ EverMemOS is ready to use!

Services running:
  • MongoDB: localhost:27017
  • Elasticsearch: localhost:19200
  • Milvus: localhost:19530
  • Redis: localhost:6379

Configuration: .env.docker

Next steps:
  1. Configure API keys in .env file
  2. Start EverMemOS: uv run python src/run.py --port 1995
  3. Check status: docker ps
  4. View logs: docker-compose logs -f

To stop services:
  docker-compose down
```

## Configuration Details

### Docker Compose Services

The setup creates the following Docker containers:

#### MongoDB
- **Image**: mongo:7.0
- **Container**: memsys-mongodb
- **Port**: 27017
- **Username**: admin
- **Password**: memsys123
- **Database**: memsys
- **Volume**: mongodb_data

#### Elasticsearch
- **Image**: elasticsearch:8.11.0
- **Container**: memsys-elasticsearch
- **Ports**: 19200 (HTTP), 19300 (Transport)
- **Mode**: Single-node
- **Security**: Disabled for development
- **Volume**: elasticsearch_data

#### Milvus
- **Image**: milvusdb/milvus:v2.5.2
- **Container**: memsys-milvus-standalone
- **Ports**: 19530 (gRPC), 9091 (Metrics)
- **Dependencies**: etcd, MinIO
- **Volume**: milvus_data

#### Redis
- **Image**: redis:7.2-alpine
- **Container**: memsys-redis
- **Port**: 6379
- **Volume**: redis_data

#### Supporting Services
- **etcd** (memsys-milvus-etcd): Milvus metadata storage
- **MinIO** (memsys-milvus-minio): Milvus object storage

### Environment Variables

The `.env.docker` file contains:

```bash
# MongoDB Configuration
MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_USERNAME=admin
MONGODB_PASSWORD=memsys123
MONGODB_DATABASE=memsys
MONGODB_URI_PARAMS=socketTimeoutMS=15000&authSource=admin

# Elasticsearch Configuration
ES_HOSTS=http://localhost:19200
ES_USERNAME=
ES_PASSWORD=
ES_VERIFY_CERTS=false
SELF_ES_INDEX_NS=memsys

# Milvus Configuration
MILVUS_HOST=localhost
MILVUS_PORT=19530
SELF_MILVUS_COLLECTION_NS=memsys

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=8
REDIS_SSL=false

# KV Storage Configuration
KV_STORAGE_TYPE=inmemory

# Server Configuration
API_BASE_URL=http://localhost:1995

# Logging
LOG_LEVEL=INFO
ENV=dev
MEMORY_LANGUAGE=en
```

## System Requirements

### Minimum Requirements
- **OS**: Linux (Ubuntu, Debian, RHEL, CentOS, Fedora) or macOS
- **Python**: 3.8 or higher
- **RAM**: 4GB minimum, 8GB recommended
- **Disk**: 10GB free space
- **Docker**: Installed or will be auto-installed
- **Ports**: 27017, 9200, 19530 available

### Supported Platforms
- ✅ Ubuntu 18.04+
- ✅ Debian 10+
- ✅ RHEL 8+
- ✅ CentOS 8+
- ✅ Fedora 33+
- ✅ macOS 11+ (Big Sur or later)

## Troubleshooting

### Docker Not Starting

If Docker fails to start:
```bash
# Check Docker status
sudo systemctl status docker

# Start Docker manually
sudo systemctl start docker

# Check if user is in docker group
groups | grep docker

# If not in docker group, log out and back in
```

### Port Conflicts

If ports are already in use:
```bash
# Check what's using the ports
sudo netstat -tulpn | grep -E '27017|9200|19530'

# Stop conflicting services or change ports in docker-compose.yml
```

### Services Not Healthy

If services fail health checks:
```bash
# Check container logs
docker-compose logs mongodb
docker-compose logs elasticsearch
docker-compose logs milvus-standalone

# Restart services
docker-compose restart

# Or rebuild
docker-compose down
docker-compose up -d
```

### macOS Docker Desktop Not Running

If Docker Desktop isn't running on macOS:
1. Open Docker Desktop from Applications
2. Wait for the Docker icon to show in menu bar
3. Verify with: `docker ps`
4. Re-run setup

## Advanced Usage

### Check Container Status

```bash
# List running containers
docker ps

# Check specific service logs
docker-compose logs -f mongodb
docker-compose logs -f elasticsearch
docker-compose logs -f milvus-standalone
```

### Access Services Directly

```bash
# MongoDB
docker exec -it memsys-mongodb mongosh -u admin -p memsys123 --authenticationDatabase admin

# Elasticsearch
curl http://localhost:19200

# Redis
docker exec -it memsys-redis redis-cli

# Check Milvus
docker exec -it memsys-milvus-standalone /bin/bash
```

### Manage Docker Services

```bash
# Stop all services
docker-compose down

# Start all services
docker-compose up -d

# Restart a specific service
docker-compose restart mongodb

# Remove all data (careful!)
docker-compose down -v
```

### Update Services

```bash
# Pull latest images
docker-compose pull

# Rebuild and restart
docker-compose up -d --force-recreate
```

## Security Notes

### Development Settings
- MongoDB credentials: `admin/memsys123` (change in production)
- Elasticsearch security is disabled (enable in production)
- Redis has no password (add password in production)
- Services exposed on localhost only

### Production Recommendations
1. Change MongoDB password
2. Enable Elasticsearch security
3. Use Docker secrets for credentials
4. Configure firewall rules
5. Enable SSL/TLS
6. Regular backups

## Integration with Other Skills

This skill works with:
- **`/evermemos-start`** - Start/stop/manage EverMemOS service
- **`/evermemos-doctor`** - Health checks and diagnostics
- **`/evermemos`** - Use EverMemOS memory features

Typical workflow:
```bash
# 1. Install and configure
/evermemos-setup

# 2. Start EverMemOS
/evermemos-start

# 3. Check health
/evermemos-doctor

# 4. Use memory features
/evermemos store "Remember this important information"
```

## Files Created

After successful setup:

```
EverMemOS/
├── docker-compose.yml          # Docker services configuration
├── .env.docker                 # Environment variables
├── data/                       # Application data directory
└── [Docker volumes]
    ├── mongodb_data/           # MongoDB data
    ├── elasticsearch_data/     # Elasticsearch data
    ├── milvus_data/            # Milvus vector data
    ├── milvus_etcd_data/       # Milvus metadata
    ├── milvus_minio_data/      # Milvus object storage
    └── redis_data/             # Redis cache data
```

## Support

If you encounter issues:

1. **Check logs**: `docker-compose logs`
2. **Verify Docker**: `docker ps`
3. **Run diagnostics**: `/evermemos-doctor`
4. **Check documentation**: `README.md` in project root

## Technical Details

### Implementation
- **Script**: `claude-skills/evermemos-setup/scripts/setup.py`
- **Entry Point**: Main `SetupManager` class
- **Docker Installation**: Auto-detects OS and installs Docker if needed
- **Compose Installation**: Auto-installs Docker Compose plugin
- **Service Configuration**: Generates docker-compose.yml dynamically

### Auto-Installation Features
- Interactive user prompts for permission
- OS detection (Linux distro, macOS)
- Progress indication during installation
- Comprehensive error handling
- Troubleshooting guidance
- Manual fallback instructions

### Verification
- All functionality verified with automated tests
- Safe to run without breaking existing installations
- Idempotent - can be run multiple times safely

---

**Version**: 2.0 (Simplified, Docker-only)
**Last Updated**: 2026-02-06
**Status**: Production Ready
