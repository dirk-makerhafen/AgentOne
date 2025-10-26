import os
import warnings
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

AGENT_SERVER_SECRET_KEY = "change_me"
SECRET_KEY = 'change_me'
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
    'config',
    'agents',
    'core',
    'providers',
    'systems',
    'launcher',
    'tools.base',
    'tools.calls',
    'tools.definitions',
    'tools.instances',
    'tools.builtin_a2a',
    'tools.builtin_filesystem',
    'tools.builtin_memory',
    'tools.builtin_python',
    'tools.builtin_shell',
    'tools.builtin_subscriptions',
    'tools.builtin_userinteraction',
    'tools.builtin_subagents',
    'tools.builtin_kv_storage',
    'ui',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_celery_results',
    'channels',
    'django_celery_beat'
)

CELERY_RESULT_BACKEND = REDIS_URL
CELERY_BROKER_URL = REDIS_URL
CELERY_WORKER_REDIRECT_STDOUTS = False
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers.DatabaseScheduler'

MIDDLEWARE = (
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # Add WhiteNoise here
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
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

DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000

LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL, # Assumes Redis is running on localhost:6379
    }
}

warnings.filterwarnings(
    'ignore',
    message='Accessing the database during app initialization is discouraged',
    category=RuntimeWarning
)