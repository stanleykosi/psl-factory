"""Isolate concurrent department suites on the Railway test service."""

import os
import re
from django.core.exceptions import ImproperlyConfigured
from .specialist_acceptance import *

group = os.environ.get("PSL_STATION_SUITE")
run = os.environ.get("PSL_STATION_RUN", "")
if os.environ.get("RAILWAY_SERVICE_NAME") != "psl-design-checks" or group not in (
    "pmo", "accounts", "operations", "roles", "original", "surface", "directory", "cutover", "api-only", "project-api", "delivery-api", "planning-api", "payroll-api", "setup-api", "hr-api", "recover-api", "go-live-api", "staff-api", "money-api", "decide-api", "report-api", "cost-api", "scope-api", "close-api", "cash-api", "change-api", "bid-api", "private-api", "source-api", "journey-api", "final-api",
):
    raise ImproperlyConfigured("A named suite on the isolated checks service is required.")
if not re.fullmatch(r"[0-9a-f]{32}", run):
    raise ImproperlyConfigured("A fresh synthetic suite run is required.")
DATABASES["default"]["TEST"] = {"NAME": f"test_psl_stations_{group}_{run}"}
