"""Current source-owned AF13 review metadata; no copied acceptance or pilot dispatch."""
from django.core.exceptions import ValidationError
from apps.identity.services import require
from apps.documents import validation as af13
from apps.documents.validation_models import ValidationReview,ValidationReplay,DiscoverySource
from apps.documents.native_validation import native


def read(actor,case,pk):
    require(actor,case,'validation.read');require(actor,case,'validation.export')
    r=ValidationReview.objects.select_related('package__case').filter(pk=pk,package__case=case,kind='acceptance').first()
    if not r:raise ValidationError('Exact same-case AF13 acceptance review required')
    af13._private_access(actor,r.package)
    report=af13.acceptance_report(actor,case.pk,r.pk)
    rows=list(ValidationReplay.objects.filter(package=r.package).order_by('pk'))
    current={}
    for row in rows:current[row.example_id]=row
    native_rows=[row for row in current.values() if native(row)]
    return {'review':r.pk,'package':r.package_id,'package_sha256':r.package.sha256,
        'level':r.package.payload['level'],'process_ids':r.package.payload['process_ids'],
        'current':report['requested_record_is_current'],'verdict':r.verdict,
        'sources':[{'id':s.pk,'sha256':s.sha256,'classification':s.metadata['classification']} for s in DiscoverySource.objects.filter(case=case,pk__in=r.package.payload['source_ids']).order_by('pk')],
        'native_evaluations':[{'id':row.pk,'family':row.provenance['family'],'job':row.provenance['job'],'sha256':row.result['actual_sha256'],'classification':row.provenance['evidence_class']} for row in native_rows],
        'native_execution_only':bool(native_rows) and len(native_rows)==len(current),
        'source_owned_human_decision':True,'oracle_binding':report['status']['costing_readiness'],
        'business_oracle_verified':False,'live_pilot_performed':False,'deployment_authorized':False}
