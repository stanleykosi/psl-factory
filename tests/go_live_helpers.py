"""Explicit SYNTHETIC decisions for local tests, never production inference."""
from django.utils import timezone
from apps.core.models import Evidence
from apps.documents.models import PublicationReceipt
from apps.pmo.delivery import latest
from apps.pmo.go_live_attestations import PROTOCOL, PURPOSE, pin, subject_pins


def attestation(f, receipt, pm, client, actor=None, signed_at=None):
    receipt = receipt if hasattr(receipt, 'publication') else PublicationReceipt.objects.get(pk=receipt)
    pm = pm if hasattr(pm, 'sha256') else Evidence.objects.get(pk=pm)
    client = client if hasattr(client, 'sha256') else Evidence.objects.get(pk=client)
    # Test declares a new synthetic event NOW, independently of evidence upload time.
    signed_at = signed_at or timezone.now().isoformat()
    return dict(subject_pins(f.d, receipt, latest(f.d, 'release_outcome')),
        protocol=PROTOCOL, purpose=PURPOSE, attesting_actor_id=(actor or f.actor).pk,
        signatures={role:dict(evidence=pin(e),source_system='synthetic-local-test',
            source_reference='signature:'+str(e.pk),decision_id='decision:'+str(e.pk),decision_version='1',
            signer_reference='synthetic:'+role,purpose=PURPOSE,signed_at=signed_at)
            for role,e in [('PM',pm),('Client',client)]})
