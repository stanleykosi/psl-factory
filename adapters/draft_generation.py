"""Explicit synthetic transport only. Durable mock store represents the external flow.

Operational Power Automate URL, credentials, authenticated original-operation lookup,
capability and output evidence must be supplied by a separately reviewed adapter.
"""
import json
from pathlib import Path
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.documents.contracts import digest

class MockDraftGenerationAdapter:
    implementation = 'mock_draft_generation_v1'

    def __init__(self, directory, *, timeout_after_create=False, lookup_unknown=False):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.timeout_after_create = timeout_after_create
        self.lookup_unknown = lookup_unknown

    def path(self, intent):
        return self.directory / (digest([intent['tenant'], intent['operation_key']]) + '.json')

    def envelope(self, intent, result):
        return dict(result, schema='draft-generation-observation/v1', operation_key=intent['operation_key'],
                    intent_sha256=digest(intent), tenant=intent['tenant'], case=intent['case'],
                    observed_at=timezone.now().isoformat())

    def generate(self, intent):
        path = self.path(intent)
        result = {'outcome': 'found', 'run_id': 'mock-run-' + digest(intent)[:20],
                  'document_ref': intent['output_contract']['document_ref'], 'document_version': '1',
                  'document_sha256': digest({'batch': intent['batch_sha256'], 'document': intent['output_contract']['document_ref']}),
                  'generated': True, 'posted': False, 'sent': False}
        # Exclusive creation, not overwriting a previous remote operation after restart.
        try:
            with path.open('x', encoding='utf-8') as stream:
                json.dump({'intent_sha256': digest(intent), 'result': result}, stream)
                stream.flush()
                import os
                os.fsync(stream.fileno())
        except FileExistsError:
            stored = json.loads(path.read_text())
            if stored['intent_sha256'] != digest(intent):
                raise ValidationError('External operation key payload conflict')
            result = stored['result']
        if self.timeout_after_create:
            raise TimeoutError('Mock transport timed out after external creation')
        return self.envelope(intent, result)

    def lookup(self, intent):
        if self.lookup_unknown or not self.path(intent).exists():
            return self.envelope(intent, {'outcome': 'unknown' if self.lookup_unknown else 'not_found',
                'run_id': None, 'document_ref': None, 'document_version': None, 'document_sha256': None,
                'generated': None, 'posted': None, 'sent': None})
        stored = json.loads(self.path(intent).read_text())
        if stored['intent_sha256'] != digest(intent):
            raise ValidationError('External original-operation payload conflict')
        return self.envelope(intent, stored['result'])


def configured_adapter(case):
    from django.conf import settings
    directory = getattr(settings, 'DRAFT_GENERATION_MOCK_DIRECTORY', None)
    if not case.synthetic or not directory:
        raise ValidationError('Only explicit synthetic draft-generator setup is available; operational Power Automate setup remains unavailable')
    return MockDraftGenerationAdapter(directory)
