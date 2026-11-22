# Deployment guide

## Prerequisites

- Python 3.10+
- MySQL 8+ (or MariaDB 10.5+) — optional, SQLite works for development
- Redis 6+
- tmux + `libtmux` (Python package, in `requirements.txt`) — required for persistent agent terminals. On Windows the installer downloads psmux (a native tmux-compatible binary) into `~/.agentone/var/bin/`; without any tmux binary the `terminal_*` tools return an error
- Supervisor (recommended) or systemd; on Windows, the built-in `sc.exe`
  service backend (`python manage.py server service install`, run as admin)
- Nginx (recommended as reverse proxy)

Redis has no fallback on any platform: the Celery broker/result backend,
Channels layer and Django cache all require a running Redis server. A native
Windows Redis build or WSL is fine; the rest of the app is native-Windows safe.

## Bootstrap

The cross-platform installer clones the repo, creates a virtual environment,
installs dependencies, runs the setup wizard and the initial
migrate/collectstatic/reload_all. It needs only Python 3.10+ and git:

```bash
curl -fsSL https://raw.githubusercontent.com/dirk-makerhafen/AgentOne/main/install.py | python3 -
# Windows PowerShell: irm .../install.py | python -
```

Run `python install.py --help` for `--dir`, `--branch`, `--skip-setup`,
`--skip-browser`, `--skip-terminal-binaries` and the deprecated `--with-browser`
no-op. The Camoufox browser build is downloaded by default. `install.sh` remains as a compatibility shim for existing
links. The rest of this guide assumes you already have a checkout and a
`config/settings_local.py`.

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
venv/bin/python manage.py server setup
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

AgentOne generates stable, per-install Django and client-registration secrets
under `~/.agentone/` with owner-only permissions when no explicit values are
configured. The defaults disable Django debug mode and accept only localhost;
set `ALLOWED_HOSTS` to the deployment's actual hostnames before exposing the
server. The setup wizard writes the same safe host default.

The API is currently single-tenant: authenticated users may read API data, but
only staff users may mutate system-wide agents, sessions, task calls,
collections, and cron jobs. Do not create untrusted staff accounts;
object-level tenancy is not implemented.

### 3. Static files

```bash
venv/bin/python manage.py collectstatic --noinput
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

### 4a. Updates and service restarts

`venv/bin/python manage.py server update` performs the full pipeline: fast-forward pull,
`pip install -r requirements.txt`, `migrate`, `collectstatic`, and `reload_all`.
It refuses a dirty worktree (use `--allow-dirty` only if you know what you are
doing) and only runs the pipeline when the remote actually moved ahead, unless
`--force` is given.

Running Python code is cached by the web/Celery processes, so a restart is
required after an update. The updater auto-detects supervisor, systemd or
launchd and spawns a detached helper that restarts the service a few seconds
later. When the service user lacks permission (common with `sudo`), set an
explicit command in `config/settings_local.py`:

```python
AGENTONE_RESTART_COMMAND = ["sudo", "-n", "supervisorctl", "restart", "agentone-server"]
# or: ["sudo", "-n", "systemctl", "restart", "agentone_server.service"]
```

Use `AGENTONE_SERVICE_MANAGER` (`auto`/`supervisor`/`systemd`/`launchd`/`windows`)
and `AGENTONE_SERVICE_NAME` to pin auto-detection. On Windows the default
service name is `agentone_server`; the updater spawns a detached PowerShell
helper that stops it, waits for `STOPPED` and starts it again (the service
account needs permission to do so). `server run` itself is platform-safe: it
chdirs to the checkout and prepends the venv's `Scripts` folder to `PATH`, so
TLS certs and console scripts work under `sc.exe`, and Celery starts with
`--pool threads` (override via `AGENTONE_CELERY_POOL` /
`AGENTONE_CELERY_CONCURRENCY`). Pass `--no-restart` to skip the restart
entirely (for example when doing a rolling deploy yourself). Set
`AGENTONE_UPDATE_CHECK_ENABLED = False` to disable the remote "Check for
updates" lookup entirely (useful on air-gapped installs). `collectstatic` is
skipped when `DEBUG` is on, since static files are served from source then.

Native Windows runs persistent `terminal_*` tools through **psmux**, which the
installer downloads into `~/.agentone/var/bin/` as `tmux.exe` (pinned release,
SHA-256 verified). No admin rights or PATH edits are needed; set
`AGENTONE_TMUX_BINARY` to use a custom binary or `--skip-terminal-binaries` to
skip the download. Git for Windows supplies the bash shell used by the
terminal sentinel — `AGENTONE_BASH` overrides its location. The browser daemon,
ad-hoc flow bridge and ingress locks use cross-platform sockets/locks;
`mysqlclient` is skipped on Windows in favour of PyMySQL.

Staff users can trigger the same pipeline from **Settings → System → Update
AgentOne**; it queues `agentone.update` on Celery and streams logs into the
panel. The panel also reports the installed version (git describe with the
`VERSION` file as fallback), commit and branch; **Check for updates** refreshes
the cached remote commit.

### 5. Nginx reverse proxy

```nginx
upstream agentone {
    server 127.0.0.1:7999;
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
| `tasks.tick_scheduler_recovery` | 60 seconds | Error recovery pass (lost messages, orphaned runs, stale queries) |
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
tar czf runtime_backup_$(date +%Y%m%d).tar.gz ~/.agentone/var/cache/runtime/

# Session-private storage (scratch files, temp memory, ad-hoc artifacts)
tar czf sessions_backup_$(date +%Y%m%d).tar.gz ~/.agentone/var/sessions/

# Local configuration
cp config/settings_local.py config/settings_local.py.backup
```

## Scaling notes

- Celery workers can be scaled horizontally by running additional worker processes (or on separate machines sharing the same Redis and MySQL).
- Rate limiting uses Redis — ensure Redis availability under load.
- The 5s tick scheduler is the heartbeat of the task system. If the beat process is down, no task state transitions will occur.

---

**See also:** [Architecture](architecture.md) · [Development guide](development.md) · [User guide](user-guide.md)
