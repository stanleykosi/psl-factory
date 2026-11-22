"""Read the reviewed state assertions and validate recorded Railway evidence."""

from collections import Counter
import csv
import json
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from uuid import UUID


DESIGN = Path(__file__).resolve().parents[1] / 'docs' / 'design'
PLAN = DESIGN / 'api-state-replay-plan.csv'
RESULTS = DESIGN / 'api-state-replay-results.csv'
FIELDS = ('state_id', 'suite', 'test', 'required_responses', 'behavior')
RESULT_FIELDS = (*FIELDS, 'result', 'deployment', 'revision', 'observed')
MARKER = 'PSL_API_STATE_REPLAY='
TEST_LABEL = re.compile(r'tests\.test_\w+\.\w+\.test_\w+')
RESPONSE = re.compile(r'\w+:[1-5]\d\d')
SUITES = {'shared', 'commercial', 'project_delivery', 'finance_reporting'}


def read_plan():
    with (DESIGN / 'screen-state-inventory.csv').open(encoding='utf-8-sig', newline='') as source:
        inventory = [row['state_id'] for row in csv.DictReader(source)]
    if len(inventory) != 262 or len(set(inventory)) != len(inventory):
        raise ValueError('Expected 262 unique design states.')
    with PLAN.open(encoding='utf-8', newline='') as source:
        reader = csv.DictReader(source)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError('Unexpected state replay plan columns.')
        rows = list(reader)
    ids = set()
    for row in rows:
        key = row['state_id']
        responses = (row['required_responses'] or '').split()
        if (None in row or key in ids or key not in inventory or row['suite'] not in SUITES
                or not TEST_LABEL.fullmatch(row['test'] or '') or not responses
                or not all(RESPONSE.fullmatch(item) for item in responses) or not (row['behavior'] or '').strip()):
            raise ValueError(f'Invalid or duplicate state replay {key}.')
        ids.add(key)
    if ids != set(inventory):
        raise ValueError('Missing state replay assertions: ' + ', '.join(sorted(set(inventory) - ids)))
    return inventory, rows


def pending_plan(rows):
    if not RESULTS.exists():
        return rows
    with RESULTS.open(encoding='utf-8', newline='') as stream:
        earlier = {row['state_id']: row for row in csv.DictReader(stream) if row['result'] == 'passed'}
    return [row for row in rows if any(earlier.get(row['state_id'], {}).get(field) != row[field] for field in FIELDS)]


def record_results(logs, deployment):
    """Import a complete set of available case markers from an exact Railway deployment."""
    deployment = str(UUID(deployment))
    inventory, rows = read_plan()
    planned = {row['state_id']: row for row in rows}
    prior = {}
    if RESULTS.exists():
        with RESULTS.open(encoding='utf-8', newline='') as source:
            prior = {row['state_id']: row for row in csv.DictReader(source)}
    observed = {}
    for line in logs.splitlines():
        if MARKER not in line:
            continue
        row = json.loads(line.split(MARKER, 1)[1])
        key = row['state_id']
        if (key not in planned or any(row[field] != planned[key][field] for field in FIELDS)
                or row['deployment'] != deployment or not re.fullmatch(r'[0-9a-f]{40}', row['revision'])
                or row['result'] not in ('passed', 'failed')):
            raise ValueError(f'Unexpected replay evidence for {key}.')
        replies = Counter(dict(row['observed']))
        if row['result'] == 'passed' and Counter(row['required_responses'].split()) - replies:
            raise ValueError(f'The successful replay for {key} lacks its required responses.')
        if key in observed and observed[key] != row:
            raise ValueError(f'Inconsistent results for {key} in this deployment.')
        observed[key] = row
    if not observed:
        raise ValueError('No state replay evidence found in the deployment logs.')
    with NamedTemporaryFile('w', encoding='utf-8', newline='', dir=RESULTS.parent, delete_on_close=False) as output:
        writer = csv.DictWriter(output, RESULT_FIELDS, lineterminator='\n')
        writer.writeheader()
        counts = Counter()
        for key in inventory:
            plan = planned.get(key, {'state_id': key})
            previous = prior.get(key, {})
            if key in observed:
                result = {field: observed[key][field] for field in RESULT_FIELDS}
                result['observed'] = ' '.join(f'{key}×{count}' for key, count in result['observed'])
            elif previous.get('result') in ('passed', 'failed') and all(
                    previous.get(field) == plan.get(field) for field in FIELDS):
                result = previous
            else:
                result = {**plan, 'result': 'pending'}
            writer.writerow(result)
            counts[result['result']] += 1
        output.close()
        Path(output.name).replace(RESULTS)
    return dict(counts)
