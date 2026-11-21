"""Isolate concurrent department suites on the Railway test service."""

import os
from django.core.exceptions import ImproperlyConfigured
from .specialist_acceptance import *

group = os.environ.get("PSL_STATION_SUITE")
if os.environ.get("RAILWAY_SERVICE_NAME") != "psl-design-checks" or group not in ("pmo", "accounts", "operations"):
    raise ImproperlyConfigured("A named suite on the isolated checks service is required.")
DATABASES["default"]["TEST"] = {"NAME": f"test_psl_stations_{group}"}
