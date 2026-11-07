"""Explicit synthetic owner artifact/receipt payloads. No default real identity."""
def target_payload(evidence, version='v2', ref='synthetic:ui/work-design'):
    return {'protocol':'ui-target/v1', 'artifact_ref':ref, 'artifact_version':version,
        'artifact_sha256':evidence.sha256,
        'artifact_evidence':{'id':evidence.pk,'version':evidence.version,'sha256':evidence.sha256}}


def approval_payload(target, version='receipt-17', role='Design Lead'):
    return {'protocol':'ui-approval/v1', 'source_version':version,
        'signatory_ref':'synthetic:signatory:'+role, 'decided_at':'2026-01-01T12:00:00+00:00',
        'approved_ui_target':{k:target[k] for k in ['artifact_ref','artifact_version','artifact_sha256']}}


