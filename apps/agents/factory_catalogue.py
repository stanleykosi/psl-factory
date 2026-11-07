"""ACT identifiers are reusable activity contracts, never business process IDs."""
from dataclasses import dataclass

@dataclass(frozen=True)
class ActivityContract:
    code:str
    title:str
    role:str
    trigger:str
    inputs:tuple
    preconditions:tuple
    tools:tuple
    outputs:tuple
    autonomy:str
    postcondition:str
    test_ids:tuple
    version:str='1'
    context_freshness:str='Current grants, immutable source hashes and configured maximum evidence age'
    handoff:str='Native task, domain result, command or receipt; not model conversation'
    budget:str='Shared FactoryWork token/step/child reservation, including retries'
    retry_owner:str='Factory coordinator for model reservations; selected native domain job for effect attempts'
    failure_route:str='Typed wait/refusal/owner_needed; effect_unknown reconciles before any resend'

def spec(n,title,role,tools,autonomy,post,version='1'):
    return ActivityContract(f'ACT{n:02}',title,role,'Current eligible native case event',('case','source_versions','allowed_capabilities'),('current_scope','profile','budget','legal_process_edge'),tuple(tools),('cited_result','native_record_refs','next_action'),autonomy,post,(f'AGT{n:02}',),version=version)

CATALOGUE={v.code:v for v in [
 spec(1,'Classify intake','intake',['native_intake'],'Scoped classification; ambiguous identity stays unresolved','Actual manifest process and evidence supported'),
 spec(2,'Resolve case and process','intake',['case_lookup'],'No ambiguous merge','One current authorised case/process link'),
 spec(3,'Plan next permitted work','coordinator',['capabilities','activity_dispatch'],'Only available legal steps','Plan and activity recorded before action'),
 spec(4,'Investigate evidence','investigator',['extract_evidence','billing.investigate','rfp.investigate_rfp','factory_forecast_sources.investigation','factory_reporting.investigate'],'Scoped reads; RFP investigation grants no review, submission or outcome authority','Citations resolve to exact permitted sources',version='3'),
 spec(5,'Request missing information','investigator',['HumanTask'],'Internal task only; explicit resolver','One deduplicated native task or owner_needed'),
 spec(6,'Reconcile PMO facts','pmo',['Handoff','milestone'],'Analysis/native handoff checks','Exact milestone/evidence/handoff agree'),
 spec(7,'Link current source evidence','pmo',['planning.packet','commercial_intake.read','factory_rfp.inputs','FactoryWork.source_head'],'Same-engagement native source successors; no source-body rewrite','Native provenance verified; original intake and shared allowance retained',version='2'),
 spec(8,'Prepare controlled output','domain',['billing.prepare','invoices.draft','planning.prepare','costing.run','delivery.prepare_readiness','forecast.prepare','reporting.draft_period_report'],'Draft, deterministic calculation or readiness creation; no business approval','Native calculation, source prerequisites and declared output scope agree'),
 spec(9,'Assemble decision packet','domain',['invoices.review_packet','commercial.draft_submission','rfp.prepare_response','rfp_documents.draft','documents.request_review','forecast_documents.draft','reporting.draft_period_report'],'Packet preparation only; RFP response reviews, ordered costing decisions and final outward review remain separate human commands','Exact immutable native subject and required human review are retained',version='2'),
 spec(10,'Resolve decision routing','deterministic_service',['review_authority','decision_authority'],'Resolve eligibility; never decide','Current eligible principals or owner_needed'),
 spec(11,'Carry out a permitted command','executor',['invoices.reserve','invoice_delivery.run_once','approval_routing.run_once','planning.bridge','costing.bind','commercial.propose','documents.reserve_publication','documents.run_publication_once','rfp_documents.capture_submission','rfp.dispose'],'Current native command authority and exact executor/profile/source scope; required decisions and actual RFP outcome stay human; internal requests grant no approval','Native intent/attempt receipt or exact internal handoff, or explicit unknown',version='2'),
 spec(12,'Reconcile uncertain effect','exception',['adapter.lookup'],'Original identity; no blind resend','Authoritative receipt or unresolved uncertainty'),
 spec(13,'Verify outcome','verification',['InvoiceIssue','InvoiceDelivery','PublicationReceipt','planning.current_readiness','delivery.readiness_inputs','RFPSubmission','RFPDisposition','LocalRFPAdapter.receipts'],'Deterministic acceptance only; an RFP agent success is not a customer outcome or verified delivery','Native output, current source gates and required receipts match the declared verification scope',version='2'),
 spec(14,'Diagnose exception','exception',['scoped_history'],'No refusal bypass or uncertain retry','Evidence-backed next safe action'),
 spec(15,'Explain case history','explanation',['scoped_history'],'Read only','Claims match actual source/attempt/receipt facts') ]}

class SyntheticFactoryCoordinator:
    name='synthetic_factory_v1'
    def choose(self,context):
        # Deliberately reacts to missing evidence/receipts rather than a fixed stage script.
        return {'activity':context['eligible'][0],'citations':context['evidence_ids'][:1]}
