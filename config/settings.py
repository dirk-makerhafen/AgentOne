import os
import warnings

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTONE_ROOT = os.path.join(BASE_DIR, ".agentone")

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
            "hosts": [{ "address": REDIS_URL }], # Assumes Redis is running on localhost:6379
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
CELERYD_PREFETCH_MULTIPLIER = 1
CELERYD_PREFETCH_COUNT =1
CELERY_BEAT_SCHEDULE = {
    'agentone-scheduler': {
        'task': 'tasks.tick_scheduler',
        'schedule': 5,  # seconds
    },
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
