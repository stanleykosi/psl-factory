from django.db import transaction
from apps.core.services import add_evidence,event,bump
from apps.finance.payroll import locked
from apps.finance.payroll_models import PayrollRequest,PayrollInput,PayrollRun
from apps.policy.payroll_validators import SCHEMAS
from apps.policy.services import resolve
from .models import AgentRun


def prepare_report_question(actor,publication,topic):
 """A04's closed metadata tool; no HR/payroll payload or model egress."""
 from adapters.payroll_questions import command,PACKET
 from apps.documents.contracts import validate
 from apps.finance.payroll import read_publication
 command('record',{'topic':topic})
 # Native current recipient/source checks precede even the metadata projection.
 read_publication(actor,publication.pk)
 run=PayrollRun.objects.only('sha256').get(pk=publication.run_id)
 packet={'format':'psl.payroll-report-question/v1','publication_id':publication.pk,
         'report_version':publication.version,'source_run_id':publication.run_id,'source_sha256':run.sha256,
         'period':publication.request.metadata['period'],'topic':topic,'private_payloads_read':False}
 validate(PACKET,packet)
 return packet


def received_report_context(actor, case):
    """Admit one current, acknowledged report through the existing closed metadata tool."""
    from django.core.exceptions import PermissionDenied, ValidationError
    from apps.finance.payroll_models import PayrollReportReceipt

    receipts = PayrollReportReceipt.objects.filter(actor=actor, publication__request__case=case).select_related(
        'publication__request').only('publication__run_id', 'publication__version',
                                    'publication__request__metadata').order_by('-publication_id')[:3]
    for receipt in receipts:
        try:
            return prepare_report_question(actor, receipt.publication, 'report_coverage')
        except (PermissionDenied, ValidationError):
            continue
    return None


@transaction.atomic
def investigate(actor,case_id,expected):
 c=locked(actor,case_id,'agent.payroll',expected);findings=[]
 for q in PayrollRequest.objects.filter(case=c).order_by('-pk')[:20]:
  inputs=list(q.inputs.defer('payload').order_by('-pk')[:20]);runs=list(q.runs.defer('result').order_by('-pk')[:20]);questions=[]
  providers={i.provider for i in inputs if i.metadata['accepted']}
  if providers!=set(q.metadata['providers']):questions.append('Ask the nominated payroll owners for the missing expected provider/version; never substitute a different period.')
  codes=sorted({code for r in inputs+runs for code in r.metadata.get('codes',[])})
  if any('overlap' in code for code in codes):questions.append('Ask source owners and Finance to agree precedence or intentional summation at employee/component granularity; no name-based deduplication.')
  if any('duplicate_source' in code for code in codes):questions.append('Ask the source owner to resolve conflicting staff or pay-item rows. Held rows must not be selected or added by an agent.')
  if any('row_currency' in code for code in codes):questions.append('Ask the source owner to confirm each held row’s currency against the agreed payroll currency. Do not infer currency or convert amounts.')
  if any('rule_unconfigured' in code for code in codes):questions.append('The affected row controls need an owner decision. Keep those rows held while permitted draft work continues.')
  if any('hr_' in code or 'membership' in code or 'transfer' in code for code in codes):questions.append('Route membership/source ambiguity back to HR; Finance must not edit staff facts or invent a transfer split.')
  if 'small_group_disclosure_hold' in codes:questions.append('Configured small-group protection holds all report publication, including totals that could reveal a suppressed group.')
  if any('control' in code or 'tieout' in code for code in codes):questions.append('Investigate source-to-combined and eligible-to-group reconciliation before review.')
  policies={k:resolve(k,c).status for k in SCHEMAS}
  questions += [k+': '+v+'; only its dependent action is unavailable' for k,v in policies.items() if v!='ACTIVE']
  findings.append({'request_id':q.pk,'evidence_id':q.evidence_id,'expected_providers':q.metadata['providers'],'input_refs':[{'id':i.pk,'provider':i.provider,'version':i.version,'accepted':i.metadata['accepted'],'source_sha256':i.source_sha256} for i in inputs],'run_refs':[{'id':r.pk,'kind':r.kind,'sha256':r.sha256,'status':r.metadata['status']} for r in runs],'codes':codes,'questions':questions,'policy_readiness':policies})
 e=add_evidence(actor,c.pk,'agent_payroll','Metadata-only payroll investigation; no employee IDs, amounts, HR/payroll rows or source instructions read','local:deterministic-payroll-v1');c.refresh_from_db()
 r=AgentRun.objects.create(case=c,actor=actor,evidence=e,process_id='F16',provider='deterministic-payroll-v1',result={'process_ids':['F16','F17','F18'],'findings':findings,'budget':{'requests':20,'inputs_per_request':20,'runs_per_request':20},'private_payloads_read':False,'hr_written':False,'payroll_paid':False,'review_approved':False,'provider_evaluation':'local deterministic only'})
 event(actor,c,'agent.payroll',run=r.pk);bump(c);return r
