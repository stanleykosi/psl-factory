from typing import Protocol

class GateEvidenceAdapter(Protocol):
    name:str
    def read(self,record)->dict: ...

class SyntheticGateAdapter:
    name='synthetic-gate-source-v1'
    def read(self,record):
        # Explicit synthetic provider fixture. Never interpret arbitrary evidence text as approval.
        return {'candidate_ref':record.candidate.reference,'requirements_sha256':record.candidate.requirements.sha256,
            'external_ref':record.external_ref,'source_owner':record.source_owner,'evidence_sha256':record.evidence.sha256,
            'decision':'accepted','critical_defects':0 if record.kind=='qa_exit' else None,
            'source_receipt':'synthetic:gate:'+str(record.pk)}
