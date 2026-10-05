import logging.handlers
import os
import sys
import warnings


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTONE_ROOT = os.path.join(BASE_DIR, ".agentone")

# Session-private storage: per-session isolated folders at
# <AGENTONE_SESSIONS_DIR>/<session_pk>/.  Override in settings_local.py.
AGENTONE_SESSIONS_DIR = os.path.expanduser("~/.agentone/sessions")

# ---------------------------------------------------------------------------
# Default settings — override any of these in config/settings_local.py
# ---------------------------------------------------------------------------
SECRET_KEY = 'django-insecure-change-me-in-production'
AGENT_SERVER_SECRET_KEY = 'change-me-in-production'
REDIS_URL = 'redis://localhost:6379/1'
DEBUG = True
ALLOWED_HOSTS = ["*"]

SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_AGE = 99*24*3600

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}


CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [
                { 
                    "address": REDIS_URL,  # Assumes Redis is running on localhost:6379
                    "socket_timeout": 90,  # Fixes the 5-second client-side cutoff
                }
            ], 
        },
    }
}

INSTALLED_APPS = (
    'corsheaders',
    'config',
    'server',
    'launcher',
    'registry',
    'ui',
    'sortedm2m',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_celery_results',
    'channels',
    'django_celery_beat',
    'rest_framework',
    'rest_framework_simplejwt',
    'drf_spectacular',
    'django_filters',
    'api',
)

CELERY_RESULT_BACKEND = REDIS_URL
CELERY_BROKER_URL = REDIS_URL
CELERY_WORKER_REDIRECT_STDOUTS = False
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers.DatabaseScheduler'
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_TRACK_STARTED = True
CELERY_BEAT_SCHEDULE = {
    'agentone-scheduler': {
        'task': 'tasks.tick_scheduler',
        'schedule': 10,  # seconds
    },
    'agentone-cron-scheduler': {
        'task': 'tasks.cron_scheduler',
        'schedule': 60,  # seconds
    },
    'agentone-sleep-guard-scheduler': {
        'task': 'tasks.sleep_guard_scheduler',
        'schedule': 60,  # seconds
    },
    #'agentone-heartbeat': {
    #    'task': 'server.tasks.heartbeat.poll_remote_executors_for_heartbeat',
    #    'schedule': 120,  # seconds
    #},
    #'agentone-recovery-scheduler': {
    #    'task': 'tasks.tick_scheduler_recovery',
    #    'schedule': 60,  # seconds
    #},
}

MIDDLEWARE = (
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # Add WhiteNoise here
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
)

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'ui', 'templates')], # Add this line to include app templates
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# Daphne >= 4.2.2 enforces a 1 MiB WebSocket message/frame limit by default
# (CVE-2026-44545). The UI pushes whole-view HTML in single frames, so a chat
# re-render exceeds 1 MiB and drops the socket. Raise it; 0 = unlimited.
WEBSOCKET_MAX_MESSAGE_SIZE = 16 * 1024 * 1024
WEBSOCKET_MAX_FRAME_SIZE = 16 * 1024 * 1024
# Same values, under the names `daphne`'s own `runserver` command reads.
DAPHNE_WEBSOCKET_MAX_MESSAGE_SIZE = WEBSOCKET_MAX_MESSAGE_SIZE
DAPHNE_WEBSOCKET_MAX_FRAME_SIZE = WEBSOCKET_MAX_FRAME_SIZE
# Daphne keepalive. After `ping_interval` seconds of silence from the browser,
# daphne sends a protocol-level ping and then arms a `ping_timeout` timer; if no
# data arrives back before it fires, autobahn calls `dropConnection(abort=True)`.
# That path logs only a Twisted `log.warn`, and daphne discards every Twisted log
# at verbosity <= 1, so the abort surfaces in the UI as a silent drop with no
# close code and no error. The client pings every WEBSOCKET_CLIENT_PING_INTERVAL
# ms; any stall or background-tab timer throttling longer than the timeout
# (daphne defaults are 20s/30s) kills the socket with no diagnostics.
WEBSOCKET_PING_INTERVAL = 20
WEBSOCKET_PING_TIMEOUT = 300
# Daphne verbosity. 0/1 redirects *every* Twisted log to nowhere
# (daphne/server.py: "Redirect the Twisted log to nowhere"), which hides
# autobahn's onClose(code, reason) and the keepalive/drop warnings. 2 routes
# Twisted logs through the stdlib `daphne` logger, which LOGGING below sends to
# a file. Use 3 only when hunting event-loop blocking (turns on asyncio debug).
DAPHNE_VERBOSITY = int(os.environ.get("AGENTONE_DAPHNE_VERBOSITY", "2"))

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR + "/ui/static",]
STATIC_ROOT = os.path.join(BASE_DIR, '_staticfiles')

STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

DJANGORESIZED_DEFAULT_SIZE = [1920, 1280]
DJANGORESIZED_DEFAULT_QUALITY = 90
DJANGORESIZED_DEFAULT_KEEP_META = False
DJANGORESIZED_DEFAULT_FORCE_FORMAT = 'JPEG'
DJANGORESIZED_DEFAULT_FORMAT_EXTENSIONS = {'JPEG': ".jpg"}
DJANGORESIZED_DEFAULT_NORMALIZE_ROTATION = True

DATA_UPLOAD_MAX_NUMBER_FIELDS = 65000

LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL, # Assumes Redis is running on localhost:6379
    }
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'api.pagination.StandardPagination',
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ),
    'PAGE_SIZE': 50,
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'AgentOne API',
    'DESCRIPTION': 'REST API for AgentOne agent orchestration framework',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SWAGGER_UI_SETTINGS': {
        'persistAuthorization': True,
    },
    'SECURITY': [
        {'BearerAuth': []},
        {'SessionAuth': []},
    ],
    'TAGS': [
        {'name': 'auth', 'description': 'JWT token authentication'},
        {'name': 'agents', 'description': 'Agent management and resolved capabilities'},
        {'name': 'sessions', 'description': 'Session management and task execution'},
        {'name': 'queries', 'description': 'Query history (read-only)'},
        {'name': 'collections', 'description': 'Data flow collections (streams and sets)'},
        {'name': 'cron', 'description': 'Cron job schedules'},
        {'name': 'providers', 'description': 'AI providers (read-only)'},
        {'name': 'models', 'description': 'AI models (read-only)'},
        {'name': 'skills', 'description': 'Skill definitions (read-only)'},
        {'name': 'projects', 'description': 'Project folders'},
        {'name': 'systems', 'description': 'Registered client systems'},
        {'name': 'workspaces', 'description': 'Workspace directories'},
        {'name': 'task-calls', 'description': 'Task call lifecycle (read-only)'},
        {'name': 'task-runs', 'description': 'Task run attempts (read-only)'},
        {'name': 'health', 'description': 'System health check'},
    ],
    'ENUM_NAME_OVERRIDES': {
        'TaskCallStatusEnum': ['server.models.enums.task_enums.TaskCallStatus'],
        'TaskCallStatusDetailEnum': ['server.models.enums.task_enums.TaskCallStatusDetail'],
        'TaskRunStatusEnum': ['server.models.enums.task_enums.TaskRunStatus'],
        'QueryStatusEnum': ['server.models.queries.query.QueryStatus'],
        'ResponseStatusEnum': ['server.models.queries.response.ResponseStatus'],
    },
}

from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ---------------------------------------------------------------------------
# Load local overrides from config/settings_local.py (gitignored)
# Create one with: python3 manage.py server setup
# Variables set here override everything above.
# ---------------------------------------------------------------------------
try:
    from .settings_local import *  # noqa
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
# Without this, LOGGING is empty and there is nowhere to see *why* a WebSocket
# dropped. Daphne routes Twisted/autobahn records into the stdlib "daphne"
# logger only when its verbosity is >= 2 (see DAPHNE_VERBOSITY), and autobahn
# reports the close code/reason there. WebSocket lifecycle events therefore need
# to be captured from the UI consumer itself as well.
# ---------------------------------------------------------------------------
# Logging handler hardening
# ---------------------------------------------------------------------------
# Daphne at verbosity >= 2 installs Twisted's stdio redirection, which turns
# every write to dynamic sys.stderr into a Twisted log event that is forwarded
# back into stdlib logging (STDLibLogObserver). The default
# Handler.handleError writes its diagnostics ("--- Logging error ---",
# "Call stack:", "Message:", "Arguments:") to dynamic sys.stderr — so a
# single emit() failure becomes new log records, which can fail again:
# a logging-while-logging spiral ending in "maximum recursion depth exceeded"
# ("Unable to format event ...") plus "reentrant call" on the file stream.
# These handlers run the stock implementation with sys.stderr temporarily
# pointed at the real stderr (sys.__stderr__, never redirected), which breaks
# the loop: diagnostics land on the true fd and generate no new records.
class _SafeHandlerMixin:
    def handleError(self, record):
        real, current = sys.__stderr__, sys.stderr
        if current is real:
            super().handleError(record)
            return
        sys.stderr = real
        try:
            super().handleError(record)
        finally:
            sys.stderr = current


class SafeRotatingFileHandler(_SafeHandlerMixin,
                              logging.handlers.RotatingFileHandler):
    pass


class SafeStreamHandler(_SafeHandlerMixin, logging.StreamHandler):
    pass


LOG_DIR = os.path.join(BASE_DIR, "logs")
try:
    os.makedirs(LOG_DIR, exist_ok=True)
except OSError:
    LOG_DIR = None

_HANDLERS = {
    "console": {
        # Bind the real stderr explicitly: dictConfig would otherwise capture
        # dynamic sys.stderr, which under Daphne -v >= 2 is Twisted's
        # LoggingFile (every write becomes a new log record).
        "class": "config.settings.SafeStreamHandler",
        "stream": "ext://sys.__stderr__",
    },
}
if LOG_DIR:
    _HANDLERS["file"] = {
        "class": "config.settings.SafeRotatingFileHandler",
        "filename": os.path.join(LOG_DIR, "daphne.log"),
        "maxBytes": 10 * 1024 * 1024,
        "backupCount": 5,
        "encoding": "utf-8",
    }

_ROOT_HANDLERS = ["console"] + (["file"] if LOG_DIR else [])

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        },
    },
    "handlers": _HANDLERS,
    "root": {
        "handlers": _ROOT_HANDLERS,
        "level": "INFO",
    },
    "loggers": {
        # Daphne forwards Twisted + autobahn records here at verbosity >= 2.
        # autobahn logs onClose(wasClean=, code=, reason=) and the
        # keepalive "dropping connection to peer ... abort=True" warning,
        # which is the only way to tell a ping timeout (1006, no close frame)
        # apart from a clean 1000 close or an application error (1011).
        "daphne": {
            "handlers": _ROOT_HANDLERS,
            "level": "INFO",
            "propagate": False,
        },
        "twisted": {
            "handlers": _ROOT_HANDLERS,
            "level": "INFO",
            "propagate": False,
        },
        # WebSocket lifecycle from the UI consumer. DEBUG is off by default
        # because it is chatty; raise to DEBUG to trace connect/disconnect.
        "ui.consumer": {
            "handlers": _ROOT_HANDLERS,
            "level": os.environ.get("AGENTONE_WS_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
    },
}
