"""Export the live contract or expand its cutover map against the accepted inventory."""
import csv
import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.urls import get_resolver, reverse

from apps.core.factory_api.urls import contract
from apps.workflows.process_directory import definitions


def expand_screen_map():
    root = settings.BASE_DIR
    mapping = json.loads((root / 'contracts/factory-api-screen-map.json').read_text(encoding='utf-8'))
    with (root / mapping['inventory']).open(encoding='utf-8', newline='') as source:
        inventory = list(csv.DictReader(source))
    routes = contract()['paths']
    known = set(get_resolver().reverse_dict)
    groups = mapping['screens']
    ids = [row['state_id'] for row in inventory]
    if len(ids) != len(set(ids)) or len(ids) != 262:
        raise CommandError('Expected 262 distinct accepted design states.')
    if set(groups) != {key[:6] for key in ids}:
        raise CommandError('The API screen groups do not match the inventory.')
    for group, entry in groups.items():
        for label in entry['json']:
            method, path = label.split(' ', 1)
            if method.lower() not in routes.get(mapping['api_prefix'] + path, {}):
                raise CommandError(f'{group} references an unknown API operation: {label}.')
        for name in entry['django']:
            if name not in known:
                raise CommandError(f'{group} references an unknown Django route: {name}.')
    states = [{'state_id': row['state_id'], 'board_paths': row['board_paths'].split('|'), **groups[row['state_id'][:6]]}
              for row in inventory]
    return {'inventory': len(states), 'screen_groups': len(groups), 'states': states}


def coverage():
    expanded = expand_screen_map()
    document = contract()
    methods = {'get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace'}

    def operations(spec):
        return {(method.upper(), path) for path, entry in spec['paths'].items() for method in entry if method in methods}

    native = operations(document)
    design_path = settings.BASE_DIR / 'architecture/packages/v7/openapi.json'
    prototype = operations(json.loads(design_path.read_text(encoding='utf-8')))
    groups = {row['state_id'][:6]: row for row in expanded['states']}
    processes = []
    for process, department, title, line, automatic in definitions():
        start = '/api/v1/received-bids' if automatic and line else '/api/v1/work' if line else None
        processes.append({
            'process': process, 'department': department, 'title': title, 'start_line': line,
            'intake_api': start,
            'source_guide': reverse('process_destination', args=[process, 'source']) if automatic else None,
            'tracking_api': ('/api/v1/projects/{case_id}/department-handoffs?process=' + process if automatic
                             else '/api/v1/work/{work_id}'),
            'execution': 'native_source_event' if automatic else 'start_work',
        })
    return {
        'live_paths': len(document['paths']), 'live_operations': len(native),
        'prototype_operations': len(prototype), 'shared_method_and_path_count': len(native & prototype),
        'prototype_without_exact_live_route': [f'{method} {path}' for method, path in sorted(prototype - native)],
        'screen_groups_with_native_steps': sum(bool(row['remaining']) for row in groups.values()),
        'states_in_groups_with_native_steps': sum(bool(row['remaining']) for row in expanded['states']),
        'processes': processes, **expanded,
    }


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        selection = parser.add_mutually_exclusive_group()
        selection.add_argument('--screen-map', action='store_true', help='Expand and validate the 262 accepted states.')
        selection.add_argument('--coverage', action='store_true', help='Compare prototype and live routes, screens and release processes.')
        parser.add_argument('--output', type=str, help='Write the result to the supplied path as UTF-8 JSON.')

    def handle(self, *args, **options):
        from pathlib import Path

        value = coverage() if options['coverage'] else expand_screen_map() if options['screen_map'] else contract()
        output = json.dumps(value, indent=2, ensure_ascii=True)
        if options['output']:
            Path(options['output']).write_text(output + '\n', encoding='utf-8', newline='\n')
        else:
            self.stdout.write(output)
