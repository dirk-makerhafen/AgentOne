"""
Example local settings — copy this to settings_local.py and customise.

    cp config/settings_local.example.py config/settings_local.py

Or generate one interactively:

    python3 manage.py server setup

All values shown here are the defaults from config/settings.py.
Uncomment and change only what you need.
"""

# ---------------------------------------------------------------------------
# Security — CHANGE THESE IN PRODUCTION
# ---------------------------------------------------------------------------
# SECRET_KEY = 'django-insecure-change-me-in-production'
# AGENT_SERVER_SECRET_KEY = 'change-me-in-production'
# DEBUG = False
# ALLOWED_HOSTS = ["your-domain.com"]

# ---------------------------------------------------------------------------
# Database — SQLite (default) or MySQL
# ---------------------------------------------------------------------------
# import os
# from django.conf import settings
#
# SQLite:
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': os.path.join(settings.BASE_DIR, 'db.sqlite3'),
#     }
# }

# MySQL:
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.mysql',
#         'HOST': 'localhost',
#         'PORT': '3306',
#         'NAME': 'AgentOne_v3',
#         'USER': 'root',
#         'PASSWORD': 'your-password',
#         'OPTIONS': {
#             'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
#         },
#     }
# }

# ---------------------------------------------------------------------------
# Redis — cache, channels, Celery broker/backend
# ---------------------------------------------------------------------------
# REDIS_URL = 'redis://localhost:6379/1'

# ---------------------------------------------------------------------------
# HTTP server (used by `manage.py server run`)
# ---------------------------------------------------------------------------
# LISTEN_ADDRESS = '0.0.0.0'
# LISTEN_PORT = '8001'
