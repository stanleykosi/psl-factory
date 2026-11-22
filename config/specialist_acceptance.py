"""Isolated Railway database for the synthetic specialist acceptance run."""

import os
from django.core.exceptions import ImproperlyConfigured
from .settings import *

if (os.getenv("RAILWAY_ENVIRONMENT_NAME"), os.getenv("RAILWAY_PROJECT_ID")) != (
    "design-acceptance",
    "f957481b-c6f7-43af-bc66-449a330a9d53",
):
    raise ImproperlyConfigured("Specialist acceptance requires the Railway test environment.")
database = "test_psl_specialist_loop"
if DATABASES["default"]["NAME"] == database:
    raise ImproperlyConfigured("The acceptance database must be separate from the application.")
DATABASES["default"]["TEST"] = {"NAME": database}
