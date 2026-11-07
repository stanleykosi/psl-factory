"""Explicit synthetic source decisions for tests, never production defaults."""
from django.utils import timezone
from apps.pmo.change_signatures import subject_pins,PROTOCOL,PURPOSE
from apps.pmo.go_live_attestations import pin


def declaration_for(actor,auth,receipt,pm,client):
    return dict(subject_pins(auth,receipt),protocol=PROTOCOL,purpose=PURPOSE,attesting_actor_id=actor.pk,
        signatures={role:{'evidence':pin(e),'source_system':'synthetic-owner-register',
            'source_reference':f'change-{auth.pk}-report-{receipt.publication.version_id}',
            'decision_id':f'{role}-signature-{e.pk}','decision_version':'1','signer_reference':f'synthetic-{role}',
            'purpose':PURPOSE,'signed_at':timezone.now().isoformat()} for role,e in [('PM',pm),('Client',client)]})
