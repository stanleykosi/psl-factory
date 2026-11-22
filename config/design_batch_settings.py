"""Isolated PostgreSQL databases for concurrent Railway acceptance groups."""
import os

from django.core.exceptions import ImproperlyConfigured

from .settings import *


if (os.getenv('RAILWAY_ENVIRONMENT_NAME'), os.getenv('RAILWAY_PROJECT_ID')) != (
        'design-acceptance', 'f957481b-c6f7-43af-bc66-449a330a9d53'):
    raise ImproperlyConfigured('Grouped database tests require the Railway acceptance environment.')

group = os.environ.get('PSL_DESIGN_TEST_GROUP')
if group not in {'commercial', 'project_delivery', 'finance_reporting', 'shared'}:
    raise ImproperlyConfigured('Specify one supported acceptance group.')

# The invoice crash fixture accepts the exact default isolated test database.
test_database = 'test_psl' if group == 'finance_reporting' else f'test_psl_design_{group}'
if DATABASES['default']['NAME'] == test_database:
    raise ImproperlyConfigured('The test database must differ from the configured application database.')

DATABASES['default']['TEST'] = {'NAME': test_database}
