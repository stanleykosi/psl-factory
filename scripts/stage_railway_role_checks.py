"""Build a Railway design-acceptance bundle from one committed Git tree."""
import argparse
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ('Dockerfile', 'adapters', 'apps', 'config', 'contracts', 'fixtures', 'manage.py',
           'reference', 'legacy_ui', 'requirements.lock', 'requirements.deploy.txt',
           'SOURCE-MANIFEST.json', 'scripts/railway-worker.sh')
CHECKS = ('tests', 'scripts/railway-native-stations.py', 'docs/design/screen-state-inventory.csv',
          'architecture/packages/v7/openapi.json')
GROUPS = ('pmo', 'accounts', 'operations', 'original', 'surface', 'directory', 'cutover', 'project-api', 'delivery-api', 'planning-api', 'payroll-api', 'setup-api', 'hr-api', 'recover-api', 'go-live-api', 'staff-api', 'money-api', 'decide-api', 'report-api', 'cost-api', 'scope-api', 'close-api', 'cash-api', 'change-api', 'bid-api', 'private-api', 'source-api', 'journey-api', 'final-api')


def stage(revision, service, groups, coordinator_ticket=None, design_regression=False, replay_suites=(),
          pending_replays=False):
    if groups and service != 'checks':
        raise ValueError('Test groups require the checks image.')
    if coordinator_ticket and (service != 'checks' or groups):
        raise ValueError('A live coordinator ticket requires a standalone checks image.')
    if design_regression and (service != 'checks' or groups or coordinator_ticket):
        raise ValueError('The design regression uses a standalone checks image.')
    if replay_suites and (service != 'checks' or groups or coordinator_ticket or design_regression):
        raise ValueError('State replay uses a standalone checks image.')
    if pending_replays and not replay_suites:
        raise ValueError('Pending replays require a state replay suite.')
    commit = subprocess.check_output(['git', 'rev-parse', '--verify', '--end-of-options', revision + '^{commit}'],
                                     cwd=ROOT, text=True).strip()
    parent = ROOT / '.runtime'
    parent.mkdir(exist_ok=True)
    destination = Path(tempfile.mkdtemp(prefix=f'role-{service}-{commit[:12]}-', dir=parent))
    paths = RUNTIME + (CHECKS if service == 'checks' else ())
    if coordinator_ticket:
        paths += ('scripts/railway-specialist-roles.py',)
    if design_regression or replay_suites:
        paths += ('scripts/design_acceptance_batch.py',)
    if replay_suites:
        paths += ('docs/design/api-state-replay-plan.csv',)
    if pending_replays:
        paths += ('docs/design/api-state-replay-results.csv',)
    with tempfile.TemporaryFile() as archive:
        subprocess.run(['git', 'archive', '--format=tar', commit, '--', *paths], cwd=ROOT, stdout=archive, check=True)
        archive.seek(0)
        with tarfile.open(fileobj=archive) as files:
            files.extractall(destination, filter='data')
    dockerfile = destination / 'Dockerfile'
    before_command, marker, _ = dockerfile.read_text(encoding='utf-8').partition('\nCMD ')
    if not marker:
        raise ValueError('The base Dockerfile has changed. Review its startup command.')
    if service == 'checks':
        before_command += '\nENV PSL_DJANGO_UI=1'
        before_command += ('\nCOPY tests tests\nCOPY scripts/railway-native-stations.py scripts/railway-native-stations.py'
                           '\nCOPY docs/design/screen-state-inventory.csv docs/design/screen-state-inventory.csv'
                           '\nCOPY architecture/packages/v7/openapi.json architecture/packages/v7/openapi.json')
        command = ('python manage.py check && python manage.py makemigrations --check --dry-run'
                   ' && exec python scripts/railway-native-stations.py --role-access ' + ' '.join(groups))
        if coordinator_ticket:
            before_command += '\nCOPY scripts/railway-specialist-roles.py scripts/railway-specialist-roles.py'
            command = ('python manage.py check && python manage.py makemigrations --check --dry-run && exec '
                       f'python scripts/railway-specialist-roles.py {coordinator_ticket} --coordinator')
        if design_regression:
            before_command += '\nCOPY scripts/design_acceptance_batch.py scripts/design_acceptance_batch.py'
            command = ('python manage.py check && python manage.py makemigrations --check --dry-run && exec '
                       'python scripts/design_acceptance_batch.py --parallel-groups 3 --api-contract')
        if replay_suites:
            before_command += ('\nCOPY scripts/design_acceptance_batch.py scripts/design_acceptance_batch.py'
                               '\nCOPY docs/design/api-state-replay-plan.csv docs/design/api-state-replay-plan.csv')
            suites = ' '.join(f'--suite {name}' for name in replay_suites)
            if pending_replays:
                before_command += '\nCOPY docs/design/api-state-replay-results.csv docs/design/api-state-replay-results.csv'
                suites += ' --pending-replays'
            command = ('python manage.py check && python manage.py makemigrations --check --dry-run && exec '
                       f'env PSL_API_STATE_REVISION={commit} python scripts/design_acceptance_batch.py '
                       f'--state-replay --parallel-groups 3 {suites}')
    else:
        command = ('if [ "$PSL_SERVICE_ROLE" = worker ]; then exec sh /app/railway-worker.sh; fi; '
                   'python manage.py migrate --noinput && exec gunicorn config.wsgi:application '
                   '--bind 0.0.0.0:${PORT:-8080} --workers 2 --access-logfile - --error-logfile -')
    dockerfile.write_text(before_command + '\nCMD ' + json.dumps(['sh', '-ec', command.strip()]) + '\n',
                          encoding='utf-8', newline='\n')
    restart = 'NEVER' if service == 'checks' else 'ON_FAILURE'
    (destination / 'railway.toml').write_text(
        f'[build]\nbuilder = "DOCKERFILE"\n\n[deploy]\nrestartPolicyType = "{restart}"\n', encoding='utf-8')
    (destination / '.railwayignore').write_text('**/__pycache__/\n**/*.pyc\n', encoding='utf-8')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('service', choices=('checks', 'app'))
    parser.add_argument('--revision', default='HEAD')
    parser.add_argument('--group', choices=GROUPS, action='append', default=[])
    parser.add_argument('--coordinator-ticket', type=UUID)
    parser.add_argument('--design-regression', action='store_true')
    parser.add_argument('--replay-suite', choices=('shared', 'commercial', 'project_delivery', 'finance_reporting'),
                        action='append', default=[])
    parser.add_argument('--pending-replays', action='store_true')
    args = parser.parse_args()
    print(stage(args.revision, args.service, args.group, args.coordinator_ticket, args.design_regression,
                args.replay_suite, args.pending_replays))
