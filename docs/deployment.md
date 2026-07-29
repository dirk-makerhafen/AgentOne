# Deployment guide

## Prerequisites

- Python 3.10+
- MySQL 8+ (or MariaDB 10.5+) — optional, SQLite works for development
- Redis 6+
- Supervisor (recommended) or systemd
- Nginx (recommended as reverse proxy)

## Production setup

### 1. Database

```sql
CREATE DATABASE AgentOne_v3 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'agentone'@'localhost' IDENTIFIED BY '<strong-password>';
GRANT ALL PRIVILEGES ON AgentOne_v3.* TO 'agentone'@'localhost';
FLUSH PRIVILEGES;
```

### 2. Application configuration

Run the setup wizard to generate a production configuration:

```bash
python3 manage.py server setup
```

Or create the config file manually:

```bash
cp config/settings_local.example.py config/settings_local.py
```

Key settings in `config/settings_local.py`:

```python
SECRET_KEY = "<generate-a-random-secret-key>"
DEBUG = False
ALLOWED_HOSTS = ["your-domain.com"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "AgentOne_v3",
        "USER": "agentone",
        "PASSWORD": "<strong-password>",
        "HOST": "localhost",
        "PORT": 3306,
        "OPTIONS": {"charset": "utf8mb4"},
    }
}
```

### 3. Static files

```bash
python3 manage.py collectstatic --noinput
```

Static files are served by WhiteNoise (configured in `config/settings.py`). For production, serve them through Nginx instead:

```nginx
location /static/ {
    alias /path/to/agentone/staticfiles/;
    expires 30d;
    add_header Cache-Control "public, immutable";
}
```

### 4. Run with Supervisor

Install supervisor and create config files:

```ini
# /etc/supervisor/conf.d/agentone.conf
[program:agentone-server]
command=/path/to/agentone/venv/bin/python3 manage.py server run
directory=/path/to/agentone
user=www-data
autostart=true
autorestart=true
stdout_logfile=/var/log/agentone/server.log
stderr_logfile=/var/log/agentone/server.err
environment=PATH="/path/to/agentone/venv/bin"
```

Reload supervisor:

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start agentone-server
```

### 5. Nginx reverse proxy

```nginx
upstream agentone {
    server 127.0.0.1:8001;
}

server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /etc/ssl/certs/agentone.crt;
    ssl_certificate_key /etc/ssl/private/agentone.key;

    client_max_body_size 100M;

    location /static/ {
        alias /path/to/agentone/staticfiles/;
        expires 30d;
    }

    location / {
        proxy_pass http://agentone;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }
}
```

The `proxy_set_header Upgrade` and `proxy_set_header Connection "upgrade"` directives are required for WebSocket support.

### 6. TLS / SSL

Generate a self-signed cert for testing, or use Let's Encrypt:

```bash
# Self-signed
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/private/agentone.key \
  -out /etc/ssl/certs/agentone.crt

# Let's Encrypt
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## Redis

Ensure Redis is configured for production:

```ini
# /etc/redis/redis.conf
bind 127.0.0.1
port 6379
requirepass <redis-password>    # optional
maxmemory 512mb
maxmemory-policy allkeys-lru
```

If you set a Redis password, update `config/settings_local.py`:

```python
REDIS_URL = "redis://:<password>@localhost:6379/1"
```

## Celery

Beat scheduler schedule:

| Task | Interval | Purpose |
|---|---|---|
| `tasks.tick_scheduler` | 10 seconds | Advance task calls and runs through state machine |
| `poll_remote_executors_for_heartbeat` | 120 seconds | Check remote executor health |

For production, consider using `-O fair` worker flag to prevent long tasks from starving short ones.
If running workers separately (not via `manage.py server run`):

```ini
[program:agentone-worker]
command=/path/to/agentone/venv/bin/celery -A config worker -l INFO -O fair
```

## Health checks

- Web app: `GET /` returns UI page (200 OK)
- WebSocket: connect to `ws://host/ws` (upgrades successfully)
- Celery worker: `celery -A config status` returns worker list
- Celery beat: `celery -A config beat --info` shows beat status

## Backup

```bash
# MySQL
mysqldump -u agentone -p AgentOne_v3 > backup_$(date +%Y%m%d).sql

# SQLite (just copy the file)
cp db.sqlite3 backup_$(date +%Y%m%d).sqlite3

# Runtime data
tar czf runtime_backup_$(date +%Y%m%d).tar.gz ~/.agentone/runtime/

# Local configuration
cp config/settings_local.py config/settings_local.py.backup
```

## Scaling notes

- The `PyHtmlGuiConsumer` uses a **single shared instance** — all WebSocket connections share one `UiApp` data model. For multi-user scenarios, this would need architectural changes.
- Celery workers can be scaled horizontally by running additional worker processes (or on separate machines sharing the same Redis and MySQL).
- Rate limiting uses Redis — ensure Redis availability under load.
- The 5s tick scheduler is the heartbeat of the task system. If the beat process is down, no task state transitions will occur.

---

**See also:** [Architecture](architecture.md) · [Development guide](development.md) · [User guide](user-guide.md)
