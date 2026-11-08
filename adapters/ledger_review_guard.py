"""F01 review preview. Public review evidence only; never a Finance decision."""
from django.core.exceptions import PermissionDenied
from apps.core.models import Evidence
from apps.core.evidence_access import public_evidence
from apps.finance import ledger
from apps.documents.contracts import digest


def readable(actor,case,args):
    ledger.readable(actor,case)  # Before any subject/evidence lookup.
    if not public_evidence(Evidence.objects.filter(case=case,pk=args['ledger_review_evidence_id'])).exists():
        raise PermissionDenied('Preview requires permitted public review evidence')


def guard(actor,case,ledger_check_id,ledger_review_evidence_id,ledger_verdict):
    args={'ledger_review_evidence_id':ledger_review_evidence_id}
    readable(actor,case,args)
    x,authority,evidence=ledger.guard_review(actor,case,ledger_check_id,ledger_review_evidence_id,ledger_verdict)
    return x,{'authority':authority,'verification_id':x.pk,'verification_sha256':digest(x.payload),
        'source_sha256':digest(x.lineage.payload),'review_evidence_sha256':evidence.sha256,
        'verdict':ledger_verdict,'scope':'native_review_public_evidence_only','business_approval':False},None


def head(observer,case,args):
    readable(observer,case,args)
    x=ledger.LedgerCheck.objects.select_related('lineage').filter(lineage__case=case,pk=args['ledger_check_id']).first()
    if not x:return None
    # Hashes only: no incumbent IDs, references, treatment, source or evidence bodies.
    return {'verification_id':x.pk,'verification_sha256':digest(x.payload),
        'source_sha256':digest(x.lineage.payload),'snapshot_sha256':digest(x.snapshot),
        'latest_check_id':x.lineage.checks.order_by('-pk').values_list('pk',flat=True).first(),
        'latest_decision_id':x.decisions.order_by('-pk').values_list('pk',flat=True).first()}
