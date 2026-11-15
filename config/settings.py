import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
from .build_identity import identity as source_identity
PROCESS_BUILD_IDENTITY = source_identity(BASE_DIR)
ENVIRONMENT = os.getenv('PSL_ENV', 'development')
DEBUG = ENVIRONMENT == 'development'
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'loggers': {'django.request': {'handlers': ['console'], 'level': 'ERROR', 'propagate': False}},
}
SECRET_KEY = os.getenv('PSL_SECRET_KEY', 'local-development-only-do-not-deploy')
if not DEBUG and SECRET_KEY == 'local-development-only-do-not-deploy':
    raise RuntimeError('PSL_SECRET_KEY is required outside development')
ALLOWED_HOSTS = os.getenv('PSL_ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',')
RAILWAY_DOMAIN = os.getenv('RAILWAY_PUBLIC_DOMAIN')
if RAILWAY_DOMAIN:
    ALLOWED_HOSTS.extend([RAILWAY_DOMAIN, 'healthcheck.railway.app'])
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = not DEBUG
    SECURE_REDIRECT_EXEMPT = [r'^health/$']
    SECURE_HSTS_SECONDS = 3600 if not DEBUG else 0
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions',
                  'django.contrib.messages', 'django.contrib.staticfiles'] + [
    f'apps.{name}' for name in ['core', 'identity', 'policy', 'workflows', 'pmo', 'finance', 'baas', 'documents', 'agents']]
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware',
              'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware',
              'django.contrib.auth.middleware.AuthenticationMiddleware', 'django.contrib.messages.middleware.MessageMiddleware',
              'django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [BASE_DIR / 'templates'],
              'APP_DIRS': True, 'OPTIONS': {'context_processors': ['django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages','apps.core.context.interface']}}]
DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql', 'NAME': os.getenv('PGDATABASE', 'psl'),
    'USER': os.getenv('PGUSER', 'psl'), 'PASSWORD': os.getenv('PGPASSWORD', ''),
    'HOST': os.getenv('PGHOST', '127.0.0.1'), 'PORT': os.getenv('PGPORT', '55432')}}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
USE_TZ = True
TIME_ZONE = 'Africa/Lagos'
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
if RAILWAY_DOMAIN:
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# A separate pre-provisioned database; never the operational/test source database.
OPERATOR_DRILL_DATABASE = os.getenv('PSL_OPERATOR_DRILL_DB') or None

# Code/deployment-owned endpoint and secret-reference registries; never supplied URLs/credentials.
READINESS_ENDPOINTS = {}
READINESS_SECRET_REFS = {}
READINESS_DATABASE_REVISION = os.getenv('PSL_READINESS_DATABASE_REVISION') or None
from .pilot_runtime import load as load_pilot_runtime
PILOT_RUNTIME_IDENTITIES = load_pilot_runtime()

# Quarantine has no application/worker activation bypass. Offline verification only.
import re
if re.match(r'^(?:test_)?psl_recovery_', DATABASES['default']['NAME']):
    raise RuntimeError('Quarantined recovery database: authentication, application startup and outbound workers are prohibited; use offline verification')
from .recovery_runtime import load as load_recovery_runtime
APPLICATION_RECOVERY = load_recovery_runtime()
from .cold_runtime import load as load_cold_runtime
COLD_RECOVERY = load_cold_runtime()
from .reconstitution_runtime import load as load_reconstitution_runtime
RECONSTITUTION = load_reconstitution_runtime()
from .native_finance_runtime import load as load_native_finance_runtime
NATIVE_FINANCE = load_native_finance_runtime()
DATABASE_ROUTERS = ['adapters.finance_readback_database.Router']
FINANCE_INBOX_SENDERS = {}  # Deployment-owned sender/key/destination/case registry; no policy secrets.
from .integration_runtime import load as load_integration_runtime
_integration_runtime=load_integration_runtime()
READINESS_ENDPOINTS=_integration_runtime['endpoints']
READINESS_SECRET_REFS=_integration_runtime['secrets']
FINANCE_INBOX_SENDERS=_integration_runtime['finance_senders']

QUICKBOOKS_READS = _integration_runtime.get('quickbooks_reads', {})
