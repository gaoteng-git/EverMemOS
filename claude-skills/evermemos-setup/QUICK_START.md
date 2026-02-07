# EverMemOS Quick Start (Simplified)

## One-Command Installation

```bash
/evermemos-setup
```

That's it! No modes, no choices. Just works.

---

## What Happens

1. ✅ Checks Python (3.8+ required)
2. ✅ Installs Docker (asks permission first)
3. ✅ Installs Docker Compose (asks permission first)
4. ✅ Installs uv and dependencies
5. ✅ Creates docker-compose.yml
6. ✅ Creates .env.docker configuration
7. ✅ Starts MongoDB, Elasticsearch, Milvus
8. ✅ Verifies all services running

---

## After Setup

### Start EverMemOS

```bash
/evermemos-start
```

### Check Status

```bash
docker ps
```

You should see 6 containers:
- memsys-mongodb
- memsys-elasticsearch
- memsys-milvus-standalone
- memsys-milvus-etcd
- memsys-milvus-minio
- memsys-redis

### Check Logs

```bash
docker-compose logs -f
```

### Stop Services

```bash
docker-compose down
```

---

## Troubleshooting

### Docker Not Running

```bash
sudo systemctl start docker
docker ps
```

### Port Conflicts

Check if ports are in use:
```bash
sudo netstat -tulpn | grep -E '27017|9200|19530'
```

### Restart Services

```bash
docker-compose restart
```

---

## Services

- **MongoDB**: localhost:27017 (user: admin, pass: memsys123)
- **Elasticsearch**: localhost:19200
- **Milvus**: localhost:19530
- **Redis**: localhost:6379

Configuration: `.env.docker`

---

**Version**: 2.0 (Simplified)
**Updated**: 2026-02-06
