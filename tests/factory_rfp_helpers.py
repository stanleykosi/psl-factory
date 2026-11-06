"""Synthetic RFP factory setup through native policy, intake and human services."""
import json
from pathlib import Path
from django.utils import timezone
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory, factory_rfp
from apps.documents.controlled import review_version
from apps.pmo import rfp, commercial
from tests import test_rfp as native
from tests.helpers import rev


def configured():
    actor,case,evidence,template,route=native.fixture()
    value=json.loads(Path('fixtures/factory-rfp.json').read_text())
    value.pop('classification')
    value.update(executor_id=actor.pk,template_id=template.pk,route_key=route['key'])
    profile=draft_operator_policy(actor,case.pk,'OPS.factory_rfp_execution',value,evidence['policy_decision'].pk,timezone.now())
    transition(actor,profile.pk,'validated');transition(actor,profile.pk,'active')
    payload={'response_evidence':evidence['rfp_response'].pk,'public_terms':evidence['rfp_commercial_terms'].pk,
        'sources':{kind:evidence[kind].pk for kind in ['requirements','plan','costing']},
        'matrix':[{'key':'R1','evidence_id':evidence['requirements'].pk,'response':'Cited coverage','disposition':'addressed'}],
        'lessons':evidence['rfp_lessons'].pk}
    return {'actor':actor,'case':case,'evidence':evidence,'template':template,'route':route,'profile':profile,'value':value,'payload':payload}


def start(data,key='RFP-FACTORY-1',payload=None):
    return factory_rfp.start(data['actor'],data['case'].pk,key,payload if payload is not None else data['payload'],
        'Synthetic bid response',rev(data['case']))


def response_review(data,work):
    response=factory_rfp.response_for(work)
    assert response is not None, work.finding
    for role in reversed(rfp.REVIEW_ROLES):
        rfp.review(data['actor'],data['case'].pk,response.pk,role,'approve',data['evidence']['policy_decision'].pk,
            'Actual synthetic review of exact response',rev(data['case']))
    return response


def costing_review(data,response):
    for role in ['PM','Head of PMO','CEO']:
        commercial.decide_proposal(data['actor'],data['case'].pk,response.commercial_id,role,'approve',
            'Actual synthetic ordered costing review',rev(data['case']))


def reviewed_document(data,work):
    factory.run_until_wait(work.pk);work.refresh_from_db()
    response=response_review(data,work);costing_review(data,response)
    factory.run_until_wait(work.pk);work.refresh_from_db()
    document=factory_rfp.document_for(work,data['value'])
    assert document is not None,work.finding
    review_version(data['actor'],data['case'].pk,document.pk,'approve','Exact client response reviewed',rev(data['case']))
    return response,document
