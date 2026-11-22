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
           'reference', 'static', 'templates', 'requirements.lock', 'requirements.deploy.txt',
           'SOURCE-MANIFEST.json', 'scripts/railway-worker.sh')
CHECKS = ('tests', 'scripts/railway-native-stations.py', 'docs/design/screen-state-inventory.csv',
          'architecture/packages/v7/openapi.json')
GROUPS = ('pmo', 'accounts', 'operations', 'original', 'surface', 'directory', 'cutover')


def stage(revision, service, groups, coordinator_ticket=None):
    if groups and service != 'checks':
        raise ValueError('Test groups require the checks image.')
    if coordinator_ticket and (service != 'checks' or groups):
        raise ValueError('A live coordinator ticket requires a standalone checks image.')
    commit = subprocess.check_output(['git', 'rev-parse', '--verify', '--end-of-options', revision + '^{commit}'],
                                     cwd=ROOT, text=True).strip()
    parent = ROOT / '.runtime'
    parent.mkdir(exist_ok=True)
    destination = Path(tempfile.mkdtemp(prefix=f'role-{service}-{commit[:12]}-', dir=parent))
    paths = RUNTIME + (CHECKS if service == 'checks' else ())
    if coordinator_ticket:
        paths += ('scripts/railway-specialist-roles.py',)
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
        before_command += ('\nCOPY tests tests\nCOPY scripts/railway-native-stations.py scripts/railway-native-stations.py'
                           '\nCOPY docs/design/screen-state-inventory.csv docs/design/screen-state-inventory.csv'
                           '\nCOPY architecture/packages/v7/openapi.json architecture/packages/v7/openapi.json')
        command = ('python manage.py check && python manage.py makemigrations --check --dry-run'
                   ' && exec python scripts/railway-native-stations.py --role-access ' + ' '.join(groups))
        if coordinator_ticket:
            before_command += '\nCOPY scripts/railway-specialist-roles.py scripts/railway-specialist-roles.py'
            command = ('python manage.py check && python manage.py makemigrations --check --dry-run && exec '
                       f'python scripts/railway-specialist-roles.py {coordinator_ticket} --coordinator')
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
    args = parser.parse_args()
    print(stage(args.revision, args.service, args.group, args.coordinator_ticket))
