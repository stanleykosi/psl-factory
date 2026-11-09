"""Local-only provisional SQL runner. Does not register a migration."""
from django.test.runner import DiscoverRunner
from django.db import connection
from scripts.local_proofs.go_live756.provisional import install
class Runner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        old = super().setup_databases(**kwargs)
        install(connection)
        return old
