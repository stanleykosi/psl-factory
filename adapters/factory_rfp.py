"""Typed native RFP operations; no approval, outcome inference or external transmission tool."""
from typing import Literal,TypedDict

class RFPSourceCitation(TypedDict):
    id: int
    kind: str
    sha256: str

class RFPInvestigation(TypedDict):
    investigation: int
    findings: list[str]
    citations: list[RFPSourceCitation]
    next_work: str
    approval_granted: Literal[False]
    submission_dispatched: Literal[False]
    external_authenticity_verified: Literal[False]

class NativeRFPAdapter:
    def investigate(self,work)->RFPInvestigation:
        from apps.agents.rfp import investigate_rfp
        run=investigate_rfp(work.execution_actor,work.case_id,work.case.revision)
        # Export a closed reference-only projection, never the whole native result
        # or private commercial source bodies. Domain records remain authoritative.
        return {'investigation':run.pk,'findings':run.result['findings'],
            'citations':[{'id':row['id'],'kind':row['kind'],'sha256':row['sha256']} for row in run.result['citations']],
            'next_work':run.result['next_work'],'approval_granted':False,'submission_dispatched':False,
            'external_authenticity_verified':False}

    def prepare(self,work,inputs):
        from apps.pmo.rfp import prepare_response
        return prepare_response(work.execution_actor,work.case_id,inputs['response_evidence'],inputs['matrix'],
            inputs['sources'],work.case.revision,public_terms_id=inputs['public_terms'])

    def draft(self,work,response,value):
        from apps.pmo.rfp_documents import draft
        return draft(work.execution_actor,work.case_id,response.pk,value['template_id'],value['route_key'],work.case.revision)

    def capture_submission(self,work,version):
        from apps.pmo.rfp_documents import capture_submission
        return capture_submission(work.execution_actor,work.case_id,version.pk,work.case.revision)

    def dispose(self,work,outcome,lessons):
        from apps.pmo.rfp import dispose
        return dispose(work.execution_actor,work.case_id,outcome.pk,lessons,work.case.revision)
