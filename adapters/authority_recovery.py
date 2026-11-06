from typing import Protocol
from django.core.exceptions import ValidationError,PermissionDenied
from apps.pmo.recoveries import request_for,request_target,target_snapshot,active_recovery


class AuthorityRecoveryAdapter(Protocol):
    def read(self,case,request_id)->dict: ...


class LocalAuthorityRecoveryAdapter:
    """Local evidence/authority comparison. No remote identity or effect claims."""
    def read(self,case,request_id):
        r=request_for(case,request_id);kind,pk=request_target(r)
        findings=[];current=None
        try:
            current=target_snapshot(case,kind,pk)
            if current!=r.snapshot:findings.append('Source/authority/policy changed; a fresh request and human decisions are required')
        except (ValidationError,PermissionDenied) as exc:findings.append(str(exc))
        decisions=list(r.decisions.order_by('pk').values('id','role','verdict','actor_id','authority','evidence_id')[:101])
        if len(decisions)>100:raise ValidationError('Recovery investigation exceeds the 100-decision budget')
        record=active_recovery(case,kind,pk)
        if not record:findings.append('No active recovery: obtain all current configured human decisions and record recovery; changed sources still require correction')
        return {'request_id':r.pk,'target_kind':kind,'target_id':pk,'requested_snapshot':r.snapshot,'current_snapshot':current,
            'decisions':decisions,'active_recovery_id':record.pk if record else None,'findings':findings,
            'source_evidence_ids':sorted({r.evidence_id,*r.snapshot['source']['evidence_ids'],*[d['evidence_id'] for d in decisions]})}
