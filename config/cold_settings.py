"""Independent control plane, never point at operational or recovered databases."""
from .settings import *
import re

if not re.fullmatch(r'(?:test_)?psl_cold_[a-z0-9_]{1,40}', DATABASES['default']['NAME']):
    raise RuntimeError('Cold control plane requires a separately provisioned psl_cold_* database')
ROOT_URLCONF = 'config.cold_urls'
SESSION_COOKIE_NAME = 'psl_cold_session'
CSRF_COOKIE_NAME = 'psl_cold_csrf'
LOGIN_REDIRECT_URL = '/'
