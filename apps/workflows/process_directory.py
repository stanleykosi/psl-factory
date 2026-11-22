"""Staff-facing entry points for the release catalogue. These rows contain no project data."""

from functools import lru_cache
from urllib.parse import urlencode

from django.urls import reverse

from apps.agents.specialists import routes
from apps.pmo.rfp_fresh_intake import LINE as RECEIVED_BID
from .factory_processes import PROCESS_IDS
from .native_station_contracts import DEFINITION
from .process_triggers import SCREENS, TRIGGERS


@lru_cache(maxsize=1)
def definitions():
    assigned = routes()
    rows = {}
    for definition, processes in PROCESS_IDS.items():
        for pid in processes:
            if pid in rows:
                raise ValueError(f"Duplicate release process {pid}.")
            spec = assigned[pid]
            line = definition if definition != DEFINITION else RECEIVED_BID if pid == 'P45' else None
            rows[pid] = (pid, spec['department'], spec['original_title'], line, definition == DEFINITION)
    return tuple(sorted(rows.values(), key=lambda row: (row[1] != 'PMO', row[0])))


def entries(available):
    """Reuse exactly the eligible intakes shown by Start work for this reader."""
    start_url = reverse('factory_create')
    rows = []
    for pid, department, title, line, handoff in definitions():
        guide = trigger_guide(pid) if handoff else None
        rows.append({
            'process': pid, 'department': department, 'title': title, 'line': line,
            'project_handoff': handoff, 'intake_available': bool(line and line in available),
            'intake_url': start_url + '?' + urlencode({'definition': line}) if line else None,
            'guide': guide,
        })
    return rows


def trigger_guide(process):
    trigger = TRIGGERS[process]
    return {
        'action': trigger.action,
        'screen': SCREENS[trigger.screen][0],
        'source_url': reverse('process_destination', args=[process, 'source']),
        'tracking_url': reverse('process_destination', args=[process, 'track']),
    }
