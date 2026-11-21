"""Export the live contract or expand its cutover map against the accepted inventory."""
import csv
import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.urls import get_resolver

from apps.core.factory_api.urls import contract


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


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument('--screen-map', action='store_true', help='Expand and validate the 262 accepted states.')

    def handle(self, *args, **options):
        value = expand_screen_map() if options['screen_map'] else contract()
        self.stdout.write(json.dumps(value, indent=2, ensure_ascii=True))
