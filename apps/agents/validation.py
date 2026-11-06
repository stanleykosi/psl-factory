"""A02/A03/A08 source comparison and bounded acceptance-gap investigation."""
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.core.services import event,bump
from apps.documents import validation as domain
from apps.documents.validation_models import DiscoverySource,ValidationExample,ValidationPackage
from .models import AgentRun

@transaction.atomic
def investigate(actor,case_id,expected):
    case=domain.locked(actor,case_id,'agent.validation',expected)
    sources=list(DiscoverySource.objects.filter(case=case).select_related('evidence').order_by('-pk')[:50]);citations=set();claims=[];conflicts=[];questions=[];versions=[]
    if not sources:raise ValidationError('Capture actual source evidence before investigation')
    by_key={}
    for s in sources:
        citations.add(s.evidence_id)
        try:domain.source_current(s);current=True
        except ValidationError:current=False
        for c in s.metadata['clauses'][:max(0,200-len(claims))]:
            claims.append({'source':s.pk,'current_source':current,'evidence':s.evidence_id,'quote':c['quote'],'locator':c['locator'],'classification':c['classification'],'process_ids':c['process_ids']})
            for p in c['process_ids']:
                key=(p,c['key']);prior=by_key.get(key)
                if prior and prior['quote']!=c['quote'] and len(conflicts)<100:conflicts.append({'process_id':p,'clause':c['key'],'source_ids':[prior['source'],s.pk],'includes_historical_source':not current or not prior['current'],'interpretation':'Different supplied text; inspect current/historical versions and applicable source precedence with the owner, no automatic approval'})
                by_key[key]={'source':s.pk,'current':current,'quote':c['quote']}
        old=DiscoverySource.objects.filter(case=case,reference=s.reference,version__lt=s.version).order_by('-version').first()
        if old:versions.append({'source':s.pk,'previous':old.pk,'changed_clause_keys':sorted({c['key'] for c in s.metadata['clauses']} ^ {c['key'] for c in old.metadata['clauses']}),'content_changed':s.evidence.sha256!=old.evidence.sha256})
    packages=[]
    for p in ValidationPackage.objects.filter(case=case,finance_handoffs__isnull=True,private_readiness_packet__isnull=True,private_protection_packet__isnull=True).order_by('-pk')[:20]:
        packages.append(domain.position(p,actor));citations.add(p.evidence_id)
        from apps.documents.native_validation import current
        from apps.documents.validation_models import ValidationReplay
        for replay in ValidationReplay.objects.filter(package=p,provenance__format__in=['psl.native-validation/v1','psl.native-validation/v2']).order_by('-pk')[:100]:
            try:current(replay,actor)
            except ValidationError:questions.append({'package':p.pk,'native_evaluation':replay.pk,'question':'Native receipt, reviewed expectations, criteria or execution heads require reassessment'})
        for g in p.payload['gaps']:
            if g['state']=='open':questions.append({'package':p.pk,'gap':g['key'],'question':g['description'],'process_ids':g['process_ids'],'human_owner_selection_required':True})
        try:domain.example_coverage(p)
        except ValidationError as exc:questions.append({'package':p.pk,'question':str(exc)})
        citations.update(ValidationExample.objects.filter(case=case,pk__in=p.payload['example_ids']).values_list('evidence_id',flat=True))
    run=AgentRun.objects.create(case=case,actor=actor,evidence=sources[0].evidence,provider='deterministic-validation-v1',process_id='P15',result={'claims':claims[:200],'conflicts':conflicts[:100],'source_comparisons':versions,'packages':packages,'draft_owner_questions':questions[:100],'citations':sorted(citations),'tools':['read_scoped_sources','compare_exact_clauses','check_example_coverage','check_current_reviews','draft_owner_question'],'budget':'50 source versions / 20 packages / 200 displayed clauses','owner_validation_granted':False,'policy_activated':False,'whole_product_accepted':False,'provider_evaluation':'local deterministic only'})
    event(actor,case,'agent.validation_investigation',run=run.pk);bump(case);return run
