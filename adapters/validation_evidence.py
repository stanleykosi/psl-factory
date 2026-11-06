"""Controlled local evidence and report inputs; supplied reports are not native execution proof."""
import json,hashlib
from django.conf import settings
from django.core.exceptions import ValidationError
from apps.documents.contracts import validate
from adapters.forecast import obj,KEY

def pack_sources():
    return {r['pack_path']:r for r in json.loads((settings.BASE_DIR/'SOURCE-MANIFEST.json').read_text(encoding='utf-8'))['files'] if r['bytes']<=100000 and r['pack_path'].endswith(('.md','.txt','.json'))}

class FrozenPackEvidenceAdapter:
    def read(self,path):
        row=pack_sources().get(path)
        if not row:raise ValidationError('Choose an allowlisted bounded frozen text source')
        data=(settings.BASE_DIR/path).read_bytes()
        if hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValidationError('Frozen source hash changed; reconcile source integrity')
        try:return data.decode('utf-8-sig'),row['sha256']
        except UnicodeDecodeError:raise ValidationError('Source is not supported UTF-8 text')

class SuppliedReplayAdapter:
    def read(self,evidence):
        try:v=json.loads(evidence.body)
        except (ValueError,TypeError):raise ValidationError('Replay report must be finite typed JSON')
        validate(obj({'example_id':{'type':'integer','minimum':1},'actual':{'type':'object'},'build_ref':KEY,'run_ref':KEY,'environment':KEY,'evidence_class':{'enum':['synthetic_fixture','reported_external']}}),v)
        return v

class LocalAcceptanceReportAdapter:
    def read(self,actor,case_id,review_id):
        from apps.documents.validation import acceptance_report
        return acceptance_report(actor,case_id,review_id)
