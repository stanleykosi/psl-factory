"""Test-only crash worker scope. No connections, provisioning or defaults changed."""
DEFAULT = 'test_psl'
OWNED = 'test_psl_sourceunit777'
SYSTEM = '7705450556148731993'
OPT_IN = 'PSL_INVOICE_CRASH_OWNED_SYSTEM'


def require(condition):
    if not condition:
        raise RuntimeError('Crash fixture requires exact isolated test database and synthetic job')


def target(env):
    name = env.get('PGDATABASE')
    if name == DEFAULT:
        require(env.get(OPT_IN) is None)
        return DEFAULT
    require(name == OWNED and env.get(OPT_IN) == SYSTEM)
    require(env.get('PGHOST') == '127.0.0.1' and env.get('PGPORT') == '55777' and env.get('PGUSER') == 'psl')
    return OWNED


def validate_connection(settings, name):
    require(name in (DEFAULT, OWNED) and settings.get('NAME') == name)
    if name == OWNED:
        require(settings.get('HOST') == '127.0.0.1' and str(settings.get('PORT')) == '55777' and settings.get('USER') == 'psl')


def verify_database(cursor, name):
    require(name in (DEFAULT, OWNED))
    if name == OWNED:
        cursor.execute('SELECT current_database(), system_identifier::text FROM pg_control_system()')
        require(cursor.fetchone() == (OWNED, SYSTEM))
    else:
        cursor.execute('SELECT current_database()')
        require(cursor.fetchone() == (DEFAULT,))


def validate_job(job):
    require(job.invoice.case.synthetic and job.kind == 'issue' and type(job.intent.get('factory_execution', {}).get('work')) is int)
