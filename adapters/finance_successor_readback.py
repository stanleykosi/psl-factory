"""Explicit opt-in native lineage metadata supplement to acknowledgement v1."""
from django.core.exceptions import ValidationError
from apps.documents.contracts import validate,digest
from apps.finance import receipt_followup as source,followup_successors as lineage
from . import native_finance as native,finance_followup_readback as base
from .finance_readback_database import provider

VERSION='psl.finance-successor-lineage/v1'

def read(mapping,projection,rules,expected_binding):
    validate(source.PROJECTION,projection)
    if any(projection[k]!=mapping.payload[k] for k in ['source_case_id','source_invoice_id','source_correction_id','variant']):raise ValidationError('Exact reviewed lineage subject required')
    public,(registry,args,secret)=native.binding(mapping)
    if public!=expected_binding:raise ValidationError('Current reviewed provider binding changed')
    with provider(args,rules,successors=True) as db:
        native.session_identity(db.connection,registry)
        if db.connection.execute("SELECT to_regclass('public.psl_native_finance_identity')").fetchone()[0] is None:raise ValidationError('Fresh Finance marker required')
        if db.connection.execute('SELECT reference,secret_sha256,contract_version FROM public.psl_native_finance_identity').fetchall()!=[(registry['identity_ref'],native.n.digest(secret),native.VERSION)]:raise ValidationError('Current Finance marker differs')
        result=base.snapshot(projection,rules,mapping.plan.case.synthetic)
        supplement={'format':VERSION,'lineage':[]}
        if result['outcome']=='acknowledged':
            # Bound every source table reachable by this installed evaluator, before ORM loads bodies.
            tables={'finance_financefollowupsuccessor':'followup_id=%s','finance_financefollowupsuccessorreview':'proposal_id IN (SELECT id FROM finance_financefollowupsuccessor WHERE followup_id=%s)'}
            def bounded(table,where,args):
                with db.cursor() as cursor:
                    cursor.execute(f'SELECT count(*),coalesce(max(octet_length(to_jsonb(t)::text)),0) FROM {table} t WHERE {where}',args)
                    row=cursor.fetchone()
                if row[0]>rules['max_records'] or row[1]>rules['max_payload_bytes']:raise ValidationError('Source lineage exceeds configured readback bounds')
            for table,where in tables.items():bounded(table,where,[int(result['request_ref'])])
            for table in ['finance_invoice','finance_invoicecorrection','policy_configuration','policy_registeredreference']:
                bounded(table,'case_id=%s',[projection['source_case_id']])
            bounded('policy_policystate','configuration_id IN (SELECT id FROM policy_configuration WHERE case_id=%s)',[projection['source_case_id']])
            for table in ['finance_invoicejob','finance_invoiceissue','finance_invoicedelivery']:
                bounded(table,'invoice_id=%s',[projection['source_invoice_id']])
            for table in ['finance_invoicecorrectionacceptance','finance_invoicecorrectiondelivery']:
                bounded(table,'correction_id IN (SELECT c.id FROM finance_invoicecorrection c JOIN finance_invoiceissue i ON i.id=c.issue_id WHERE i.invoice_id=%s)',[projection['source_invoice_id']])
            for p in lineage.Proposal.objects.filter(followup_id=int(result['request_ref'])).select_related('followup__case','original__invoice','successor__invoice','actor','evidence').defer('note','evidence__body','actor__password','actor__username','actor__first_name','actor__last_name','actor__email').order_by('-pk'):
                supplement['lineage'].append(lineage.status(p))
        if len(__import__('json').dumps(supplement).encode())>rules['max_payload_bytes']:raise ValidationError('Lineage metadata exceeds configured byte budget')
    return {**result,'format':base.VERSION,'provider_binding_sha256':digest(public),'classification':'native_postgres_finance_followup',
        'fixture_scope':'synthetic' if mapping.plan.case.synthetic else 'operational','direct_native_verification':True,'direct_vendor_verification':False,
        'password_authentication_proven':False,'execution_authorized':False,'financial_effect_verified':False,'debt_waived':False,'business_jobs_reenacted':False,
        'successors':supplement}
