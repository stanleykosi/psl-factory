"""Typed boundary between the workflow coordinator and a department's native records."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

from django.apps import apps
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Model


DEFINITION = "process-handoff/v1"
COMPONENT = "OPS.factory_native_station_execution"
PROJECTION = "native_station_projection"
PROCESSES = tuple("""
    P01 P02 P04 P05 P08 P09 P10 P11 P12 P13 P15 P17 P18 P19 P20 P21 P22 P23 P24 P25
    P27 P29 P30 P31 P38 P45 P51 P52 P53 P54 P55 P56 P58 P63
    F02 F04 F05 F06 F08 F10 F11 F14 F15 F19 F20 F24 F25 F26 F27 F28 F31 F32 F33 F34 F35
    F36 F37 F38 F40 F41 F42 F43 F45
""".split())


@dataclass(frozen=True)
class Observation:
    case: Model
    source: Model
    lines: dict[str, str]
    receipt: Model | None = None


@dataclass(frozen=True)
class Route:
    process: str
    model: str
    matches: Callable[[Model], bool]
    owner: Callable[[Model], Model]
    observe: Callable[[Model, Model], Observation]


@lru_cache(maxsize=1)
def registry():
    from apps.finance.coordinator_accounts import ROUTES as accounts
    from apps.finance.coordinator_operations import ROUTES as operations
    from apps.pmo.coordinator_routes import ROUTES as pmo
    from apps.agents.specialists import routes

    result = {}
    for route in (*pmo, *accounts, *operations):
        spec = routes().get(route.process)
        if not spec or spec["department"] not in ("PMO", "Finance") or route.process in result:
            raise ImproperlyConfigured(f"Invalid or repeated coordinator process {route.process}.")
        apps.get_model(route.model)
        result[route.process] = route
    if set(result) != set(PROCESSES):
        raise ImproperlyConfigured(f"Native coordinator station mismatch: {sorted(set(PROCESSES) ^ set(result))}")
    return result
