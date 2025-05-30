# TelosPump Bot - Docker Setup

Simple Docker containerization for the TelosPump monitoring bot.

## Quick Start

### 1. Prerequisites
- Docker and Docker Compose installed
- Your `.env` file configured with all required variables

### 2. Environment Setup
Make sure your `.env` file contains:
```bash
BOT_TOKEN=your_telegram_bot_token
CHANNEL_ID=-1002698393090
ALERTS_THREAD_ID=4
ADMIN_IDS=682998062,7525101581,7747334627
RPC_URL=https://rpc.telos.net
```

### 3. Build and Run
```bash
# Build the Docker image
docker-compose build

# Start the bot (detached mode)
docker-compose up -d

# View logs
docker-compose logs -f telospump-bot
```

## Management Commands

### Start/Stop/Restart
```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# Restart
docker-compose restart telospump-bot
```

### Monitoring
```bash
# View logs (follow mode)
docker-compose logs -f telospump-bot

# Check status
docker-compose ps

# View resource usage
docker stats telospump-bot
```

### Maintenance
```bash
# Access container shell
docker-compose exec telospump-bot /bin/bash

# Update configuration (restart required)
docker-compose restart telospump-bot

# Clean rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## File Structure

```
telospump-bot/
├── Dockerfile              # Container definition
├── docker-compose.yml      # Service configuration
├── .dockerignore           # Files to exclude from build
├── .env                     # Environment variables
├── requirements.txt         # Python dependencies
├── main.py                  # Main application
├── bot_config.json         # Bot configuration (persistent)
├── videos/                 # Video files (persistent)
└── logs/                   # Application logs (persistent)
```

## Persistent Data

The following data persists between container restarts:
- `bot_config.json` - Bot configuration and tokens
- `videos/` - Video files for alerts
- `logs/` - Application logs

## Configuration Updates

To update bot configuration:

1. **Via Admin Commands**: Use the Telegram bot admin interface
2. **Via Config File**: Edit `bot_config.json` and restart container
3. **Via Environment**: Update `.env` and restart container

## Troubleshooting

### Bot Won't Start
```bash
# Check logs
docker-compose logs telospump-bot

# Verify environment variables
docker-compose exec telospump-bot env | grep -E "BOT_TOKEN|CHANNEL_ID"
```

### Connection Issues
```bash
# Test RPC connection
docker-compose exec telospump-bot python -c "
from web3 import Web3
w3 = Web3(Web3.HTTPProvider('https://rpc.telos.net'))
print('Connected:', w3.is_connected())
"
```

### Resource Usage
```bash
# Monitor resource usage
docker stats telospump-bot

# Adjust memory limits in docker-compose.yml if needed
```

## Production Deployment

For production deployment, consider:

1. **Resource Limits**:
```yaml
services:
  telospump-bot:
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
```

2. **Health Checks**: Already included in Dockerfile

3. **Log Rotation**: Configured in docker-compose.yml

4. **Backup Strategy**: Backup `bot_config.json` and `videos/` regularly

5. **Monitoring**: Use `docker stats` or integrate with monitoring tools

## Security Notes

- Container runs as non-root user (telospump:1000)
- Sensitive data stored in environment variables
- Network isolated by default
- Minimal attack surface with slim Python image
