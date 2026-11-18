"""Prepare named synthetic cases for the state acceptance walkthrough."""
import json
import os
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from adapters.publications import InternalPublicationAdapter
from apps.core.models import Case
from apps.core.services import add_evidence
from apps.documents.controlled import review_version
from apps.documents.models import PublicationJob
from apps.finance import invoice_delivery
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant
from apps.pmo import rfp_portal, rfp_pricing
from apps.policy.role_assignments import draft as draft_roles, draft_delegations
from apps.policy.services import resolve, transition
from apps.workflows import factory, factory_minutes
from apps.workflows.models import FactoryWork
from tests import correction_helpers, document_helpers, factory_helpers, factory_rfp_helpers, planning_helpers, settlement_helpers, test_commercial_changes, test_rfp
from tests.billing_helpers import coverage, policy, stage_policy
from tests.helpers import rev, signed
from tests.test_change_impacts import ChangeImpactTests
from tests.test_factory_minutes import FactoryMinutesTests
from tests.test_factory_reporting import FactoryReportingTests, artifact


class InterruptedMinutesDelivery(InternalPublicationAdapter):
    def deliver(self, job, fence):
        raise TimeoutError('Synthetic receipt unavailable after original dispatch')


@transaction.atomic
def prepare(key, operator):
    case, created = Case.objects.get_or_create(tenant='design-state-walkthrough', kind='project', synthetic=True,
                                               title='Browser design states · ' + key)
    if key == 'money-read-only':
        Grant.objects.get_or_create(case=case, user=operator, action='case.read')
        return {'case': str(case.pk)}
    if key in {'delegation', 'delegation-periods', 'delegation-read-only'}:
        if created:
            Grant.objects.bulk_create([Grant(case=case, user=operator, action=action) for action in dict.fromkeys(ACTIONS)])
        second, _ = get_user_model().objects.get_or_create(username='state-check-delegation-recipient')
        Grant.objects.get_or_create(case=case, user=second, action='case.read')
        proof = case.evidence.filter(kind='policy_decision', source='synthetic:state-walkthrough').first()
        if proof is None:
            proof = add_evidence(operator, case.pk, 'policy_decision', 'Synthetic draft-only verification decision',
                                 'synthetic:state-walkthrough')
        if resolve('D05.role_principal_assignments', case).status != 'ACTIVE':
            role_policy = draft_roles(operator, case.pk, [{'role': 'PM', 'user_id': operator.pk},
                {'role': 'PM', 'user_id': second.pk}], proof.pk, timezone.now())
            transition(operator, role_policy.pk, 'validated')
            transition(operator, role_policy.pk, 'active')
        if key == 'delegation-periods' and resolve('D05.delegation_rules', case).status != 'ACTIVE':
            now = timezone.now()
            rules = [{'role': 'PM', 'principal_id': operator.pk, 'delegate_id': second.pk,
                      'valid_from': (now + timedelta(days=start)).isoformat(),
                      'valid_until': (now + timedelta(days=end)).isoformat()}
                     for start, end in [(-6, -4), (-2, 2), (4, 6)]]
            configured = draft_delegations(operator, case.pk, rules, proof.pk, now)
            transition(operator, configured.pk, 'validated')
            transition(operator, configured.pk, 'active')
        if key == 'delegation-read-only' and created:
            Grant.objects.filter(case=case, user=operator, action='policy.configure').update(active=False)
        return {'case': str(case.pk), 'evidence': proof.pk, 'delegate': second.pk}
    if not created:
        existing = FactoryWork.objects.filter(case=case).first()
        return {'case': str(case.pk), 'work': existing.pk if existing else None}
    Grant.objects.bulk_create([Grant(case=case, user=operator, action=action) for action in dict.fromkeys(ACTIONS)])
    if key in {'costing-proposal-review', 'costing-proposal-own', 'costing-proposal-rules'}:
        import copy
        from tests import costing_helpers
        from tests.operator_helpers import policy as operator_policy
        from apps.pmo import costing_proposals
        from apps.policy.costing_proposal_validators import COMPONENT as PROPOSAL_REVIEW

        users = get_user_model().objects
        create_user = users.create_user
        with (
            patch.object(costing_helpers, 'setup_case', return_value=(operator, case)),
            patch.object(users, 'create_user', side_effect=lambda username, **values:
                create_user(username='state-' + key + '-' + username, **values)),
        ):
            data = costing_helpers.fixture()
        proposed = copy.deepcopy(data['rule'].payload)
        proposed['calculator_version'] = 'v2'
        proposed['parameters'][0]['value'] = '12.00'
        source = costing_helpers.evidence(data, 'p14_rule', proposed)
        proposer = operator if key == 'costing-proposal-own' else data['owner']
        proposal = costing_proposals.propose(proposer, case.pk, data['rule'].pk, source.pk,
            'SAMPLE proposed hourly rate supported by revised source evidence.', 'browser-version-2')
        if key != 'costing-proposal-rules':
            reviewer = data['owner'] if key == 'costing-proposal-own' else operator
            operator_policy(data, PROPOSAL_REVIEW, {'reviewer_id': reviewer.pk,
                'reviewer_role': 'PMO' if key == 'costing-proposal-own' else 'PM',
                'independent_review': True})
        return {'case': str(case.pk), 'proposal': proposal.pk, 'rule': data['rule'].pk,
                'proof': data['review_evidence'].pk}
    if key in {'handover-external-reply', 'handover-reply-rules', 'handover-reply-gaps'}:
        from tests import test_delivery, test_handover_replies
        users = get_user_model().objects
        create_user = users.create_user
        with (
            patch.object(test_delivery, 'setup_case', return_value=(operator, case)),
            patch.object(users, 'create_user', side_effect=lambda username, **values:
                create_user(username='state-' + key + '-' + username, **values)),
        ):
            data = test_handover_replies.prepare()
            if key != 'handover-reply-rules':
                test_handover_replies.configure(data)
            if key == 'handover-reply-gaps':
                from apps.pmo.handover_replies import record_reply
                record_reply(operator, case.pk, data.d.pk, test_handover_replies.receipt(data).pk, 'gaps',
                    data.reply_proof.pk, 'SAMPLE runbook misses the export restart steps.',
                    'SAMPLE Support lead', 'email', timezone.now(), 'PM', 0, rev(case))
            revised = add_evidence(operator, case.pk, 'support_document',
                'SAMPLE revised runbook includes the export restart steps and outage contacts.', 'synthetic:revised-handover')
        return {'case': str(case.pk), 'work': data.work.pk, 'dossier': data.d.pk,
            'receipt': test_handover_replies.receipt(data).pk, 'proof': data.reply_proof.pk,
            'revised_support': revised.pk, 'policy_proof': data.e['policy_decision'].pk}
    if key in {'archive-file-receipts', 'archive-file-uncertain', 'archive-file-missing', 'archive-private-store'}:
        from tests import test_delivery
        from tests.test_project_archive_files import configured, reserve, LostCopyResponse, MissingCopyResponse
        from apps.pmo.archive_transfer import run_once
        from apps.pmo.models import ArchiveCopyJob

        users = get_user_model().objects
        create_user = users.create_user
        with (
            patch.object(test_delivery, 'setup_case', return_value=(operator, case)),
            patch.object(users, 'create_user', side_effect=lambda username, **values:
                         create_user(username='state-' + key + '-' + username, **values)),
        ):
            data = configured('private_object_store/v1' if key=='archive-private-store' else 'synthetic_archive/v1')
            plan = reserve(data)
            from apps.workflows.factory_progress import set_progress
            data.work.refresh_from_db()
            set_progress(operator,data.work.pk,data.work.revision,False)
            jobs = list(ArchiveCopyJob.objects.filter(file__plan=plan).order_by('pk'))
            for index, job in enumerate(jobs if key!='archive-private-store' else []):
                adapter = None
                if index == 0 and key == 'archive-file-uncertain':
                    adapter = LostCopyResponse()
                if index == 0 and key == 'archive-file-missing':
                    adapter = MissingCopyResponse()
                run_once(job.pk, adapter=adapter)
            if key!='archive-private-store':
                factory.run_until_wait(data.work.pk)
        return {'case': str(case.pk), 'work': data.work.pk, 'plan': plan.pk,
                'jobs': [job.pk for job in jobs], 'proof': data.e['policy_decision'].pk}
    if key in {'handover-review', 'handover-receipt', 'archive-inventory'}:
        from tests import test_delivery, test_factory_archive, test_factory_handover

        users = get_user_model().objects
        create_user = users.create_user
        with (
            patch.object(test_delivery, 'setup_case', return_value=(operator, case)),
            patch.object(users, 'create_user', side_effect=lambda username, **values:
                         create_user(username='state-' + key + '-' + username, **values)),
        ):
            if key == 'archive-inventory':
                data = test_factory_archive.setup()
                test_factory_archive.ready(data)
                selected = data.inventory
            else:
                data = test_factory_handover.setup(review=key == 'handover-review')
                test_factory_handover.ready(data)
                selected = data.inputs
                factory.run_until_wait(data.work.pk)
        return {'case': str(case.pk), 'work': data.work.pk, 'dossier': data.d.pk,
                'proof': data.e['requirements'].pk, 'inputs': selected}
    if key == 'assistant-draft':
        with patch.object(planning_helpers, 'setup_case', return_value=(operator, case)):
            planning = planning_helpers.fixture(configured=True, username='state-assistant-draft')
        return {'case': str(case.pk), 'packet': planning['packet'].pk}
    if key in {'go-live-client-changes','go-live-client-decline','go-live-client-rules','go-live-client-correction'}:
        from tests import test_delivery
        from tests.test_go_live_replies import delivered,reply
        users=get_user_model().objects
        create_user=users.create_user
        with (patch.object(test_delivery,'setup_case',return_value=(operator,case)),
              patch.object(users,'create_user',side_effect=lambda username,**values:create_user(username='state-'+key+'-'+username,**values))):
            data=delivered(configured=key!='go-live-client-rules')
            response=reply(data,'declined' if key in {'go-live-client-decline','go-live-client-correction'} else 'changes_requested')
            corrected=data.evidence('incident_reporting','Synthetic revised incident plan includes the requested fallback contact, sample-contact@example.invalid.')
            fix=data.evidence('resolution','Synthetic fix and regression evidence for the declined release.')
            correction=data.evidence('go_live_response_correction','Synthetic evidence correcting a report reference or reviewing the fixed issue.')
            factory.run_until_wait(data.work.pk)
        return {'case':str(case.pk),'work':data.work.pk,'reply':response.pk,'version':data.version.pk,
                'receipt':data.receipt.pk,'corrected_incident':corrected.pk,'fix':fix.pk,
                'correction':correction.pk,'decision':data.e['policy_decision'].pk}
    if key in {'planning-departments','planning-department-rules'}:
        from tests.test_planning_department_inputs import enhanced
        users=get_user_model().objects
        create_user=users.create_user
        with (patch.object(planning_helpers,'setup_case',return_value=(operator,case)),
              patch.object(users,'create_user',side_effect=lambda username,**values:create_user(username='state-'+key+'-'+username,**values))):
            data=enhanced(configured=key=='planning-departments')
            planning_helpers.observe(data)
            factory.run_until_wait(data['work'].pk)
        return {'case':str(case.pk),'work':data['work'].pk,'packet':data['packet'].pk,'proof':data['e']['plan'].pk,'decision':data['e']['policy_decision'].pk}
    if key in {'planning-ready','planning-owner-wait','planning-rules-needed','planning-verified'}:
        from tests.test_factory_planning import setup
        users=get_user_model().objects
        create_user=users.create_user
        with (patch.object(planning_helpers,'setup_case',return_value=(operator,case)),
              patch.object(users,'create_user',side_effect=lambda username,**values:create_user(username='state-'+key+'-'+username,**values))):
            data=setup(department_configured=key!='planning-rules-needed')
            if key!='planning-ready':factory.run_until_wait(data['work'].pk)
            if key=='planning-verified':
                planning_helpers.observe(data)
                factory.run_until_wait(data['work'].pk)
        return {'case':str(case.pk),'work':data['work'].pk,'packet':data['packet'].pk}
    if key in {'commercial-review','commercial-information'}:
        from tests import costing_helpers
        from tests.test_factory_commercial import setup
        users=get_user_model().objects
        create_user=users.create_user
        with (patch.object(costing_helpers,'setup_case',return_value=(operator,case)),
              patch.object(users,'create_user',side_effect=lambda username,**values:create_user(username='state-'+key+'-'+username,**values))):
            data=setup(missing=key=='commercial-information')
            factory.run_until_wait(data['work'].pk)
        return {'case':str(case.pk),'work':data['work'].pk,'head':data['head'].pk}
    if key in {'issue-followup','issue-owner-access','issue-verified'}:
        from tests import test_factory_issues
        log_issue=test_factory_issues.log_issue
        with (patch.object(test_factory_issues,'setup_case',return_value=(operator,case)),
              patch.object(test_factory_issues,'log_issue',side_effect=lambda actor,case_id,reference,*args:log_issue(actor,case_id,'SAMPLE-'+key.upper(),*args))):
            entry=test_factory_issues.FactoryIssueTests()
            entry.setUp()
        entry.advance()
        if key=='issue-verified':
            entry.respond()
            entry.advance()
        if key=='issue-owner-access':
            Grant.objects.filter(case=case,user=operator,action='issue.own').update(active=False)
            factory.run_until_wait(entry.work.pk)
        return {'case':str(case.pk),'work':entry.work.pk,'issue':entry.state.issue_id,'proof':entry.e['requirements'].pk}
    if key in {'bid-followup-delivery','bid-followup-manual','bid-followup-uncertain'}:
        from tests.test_rfp_messages import configured
        from apps.pmo import rfp,rfp_followup,rfp_messages
        from adapters.rfp_followup import SyntheticBidMailbox
        with patch.object(test_commercial_changes,'setup_case',return_value=(operator,case)):
            data=factory_rfp_helpers.configured(reference='SAMPLE-'+key.upper())
        configured(data,'manual_evidence' if key=='bid-followup-manual' else 'synthetic_mailbox')
        work=factory_rfp_helpers.start(data,key=key)
        response,_=factory_rfp_helpers.reviewed_document(data,work)
        factory.run_until_wait(work.pk)
        submission=response.submissions.get()
        result=rfp.outcome(operator,case.pk,submission.pk,'unknown',timezone.now(),'Client',None,
                           'Sample no-reply check',rev(case),followup_on=timezone.localdate())
        draft=rfp_followup.draft(operator,case.pk,result.pk,rev(case))
        review=rfp_followup.review(operator,case.pk,result.pk,draft.pk,'Sample reviewed bid follow-up',0,rev(case))
        if key=='bid-followup-uncertain':
            class Interrupted(SyntheticBidMailbox):
                def deliver(self,dispatch):
                    raise TimeoutError('Synthetic channel response was interrupted')
            dispatch=rfp_messages.reserve(operator,case.pk,result.pk,review.pk,'customer_followup',rev(case))
            rfp_messages.run_once(dispatch.pk,Interrupted())
        return {'case':str(case.pk),'work':work.pk,'outcome':result.pk,'review':review.pk}
    if key in {'invoice-review','invoice-returned','invoice-owner-needed','invoice-information'}:
        from tests.obligation_helpers import factory_identified
        from apps.workflows.models import HumanTask
        with patch.object(factory_helpers,'setup_case',return_value=(operator,case)):
            data=factory_helpers.fixture(missing=key=='invoice-information',responsibility=key!='invoice-owner-needed')
        work=data['work']
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        if work.invoice_id:
            factory_identified(data)
        if key=='invoice-returned':
            task=HumanTask.objects.get(case=case,kind='factory_review',status='open')
            task=factory.claim_task(operator,task.pk,task.revision)
            factory.decide(operator,task.pk,task.revision,'return',data['proof'].pk,'Synthetic invoice needs a corrected preparation.')
        return {'case':str(case.pk),'work':work.pk,'proof':data['proof'].pk}
    if key in {'stability-observations','stability-missing-rule'}:
        from tests import test_delivery
        from tests.test_factory_hypercare import setup
        from apps.documents.controlled import request_review,reserve_publication
        from apps.documents.delivery import run_publication_once
        from apps.documents.models import PublicationReceipt

        def publish_exact(fixture,version):
            if version.audience=='client':
                request_review(operator,case.pk,version.pk,rev(case))
                review_version(operator,case.pk,version.pk,'approve','Synthetic client projection',rev(case))
            publication=reserve_publication(operator,case.pk,version.pk,rev(case))
            run_publication_once(job_id=publication.job.pk)
            return PublicationReceipt.objects.get(publication=publication)

        with (patch.object(test_delivery,'setup_case',return_value=(operator,case)),
              patch.object(test_delivery.DeliveryFixture,'publish',publish_exact)):
            entry=setup()
            entry.accepted()
            if key=='stability-observations':entry.criteria()
            entry.observations(errors=2)
            factory.run_until_wait(entry.work.pk)
        return {'case':str(case.pk),'work':entry.work.pk,'dossier':entry.d.pk,'proof':entry.e['requirements'].pk}
    if key == 'bid-intake-walkthrough':
        with patch.object(test_commercial_changes, 'setup_case', return_value=(operator, case)):
            _, _, evidence, _, _ = test_rfp.fixture(record_intake=False)
        return {'case': str(case.pk), 'intake_source': evidence['rfp_intake'].pk}
    if key == 'bid-answer-review':
        with patch.object(test_commercial_changes, 'setup_case', return_value=(operator, case)):
            data = factory_rfp_helpers.configured(reference='RFP-SAMPLE-ANSWER-REVIEW')
        row = data['payload']['matrix'][0]
        data['payload']['matrix'] = [dict(row, key='R' + str(number),
            response='SAMPLE current response for requirement ' + str(number) + '.') for number in range(1, 5)]
        work = factory_rfp_helpers.start(data, key=key)
        return {'case': str(case.pk), 'work': work.pk, 'requirements': 4,
                'policy_proof': data['evidence']['policy_decision'].pk}
    if key == 'portal-pricing':
        with patch.object(test_commercial_changes, 'setup_case', return_value=(operator, case)):
            data = factory_rfp_helpers.configured(reference='RFP-SAMPLE-PORTAL-PRICING',portal=True)
        terms = add_evidence(operator, case.pk, 'rfp_commercial_terms', json.dumps({
            'schema':rfp_pricing.QUOTE,'terms':'Synthetic reviewed portal bid','amount':'100.00',
            'currency':'NGN','basis':'whole_contract'}), 'synthetic:portal-reviewed-quote')
        data['payload']['public_terms'] = terms.pk
        work = factory_rfp_helpers.start(data,key=key)
        _, version = factory_rfp_helpers.reviewed_document(data,work)
        proof = add_evidence(operator,case.pk,'rfp_portal_receipt',json.dumps({
            'schema':rfp_portal.SCHEMA,'version':version.pk,'sha256':version.payload_sha256,
            'destination':data['route']['destination_ref'],'reference':'PORTAL-ACCEPTANCE-01',
            'received_at':timezone.now().isoformat()}),'synthetic:exact-portal-receipt')
        return {'case':str(case.pk),'work':work.pk,'version':version.pk,'evidence':proof.pk}
    if key == 'corrected-money':
        run_invoice = invoice_delivery.run_once
        with (
            patch.object(settlement_helpers, 'setup_case', return_value=(operator, case)),
            patch.object(invoice_delivery, 'run_once', side_effect=lambda: run_invoice(case_id=case.pk)),
        ):
            _, _, billing, issue, evidence = correction_helpers.fixture(identity=True)
            credit = correction_helpers.note(operator, case, issue, evidence, reference='BROWSER-MONEY-CREDIT')
            correction = correction_helpers.apply(operator, case, credit, evidence)
            correction.refresh_from_db()
            if correction.status != 'confirmed':
                raise ValueError('Synthetic invoice credit was not verified')
            receipt, lot = settlement_helpers.receipt(operator, case, ref='browser-money-corrected-cash')
            settlement_helpers.assign(operator, case, receipt, billing, evidence)
            settlement_helpers.allocate(operator, case, lot, issue, '20.00', evidence)
        return {'case': str(case.pk), 'invoice': issue.invoice_id, 'credit': credit.pk, 'receipt': receipt.pk}
    if key in {'signed-money', 'known-money'}:
        agreement = signed(operator, case)['signature']
        billing = coverage(operator, case)
        stage_policy(operator, case, billing, agreement)
        if key == 'known-money':
            transition(operator, resolve('D12.stage_terms', case).configuration.pk, 'revoked')
            policy(operator, case, 'D12.stage_terms', [
                {'coverage_id': billing.pk, 'stage': 'signed_sow', 'amount': '30.00', 'due_date': '2026-11-01'},
                {'coverage_id': billing.pk, 'stage': 'uat', 'amount': '42.50', 'due_date': '2026-12-02'},
                {'coverage_id': billing.pk, 'stage': 'completion', 'amount': '63.75', 'due_date': '2026-12-16'},
            ])
            policy(operator, case, 'D12.uat_billing_predicate_ref',
                   {'coverage_id': billing.pk, 'stage': 'uat', 'milestone_name': 'Synthetic client acceptance'})
        return {'case': str(case.pk), 'agreement': agreement.pk}
    if key in {'bid-loss-walkthrough', 'bid-win-walkthrough', 'bid-award-walkthrough'}:
        with patch.object(test_commercial_changes, 'setup_case', return_value=(operator, case)):
            data = factory_rfp_helpers.configured(reference='RFP-SAMPLE-' + key.upper())
        work = factory_rfp_helpers.start(data, key=key)
        response, _ = factory_rfp_helpers.reviewed_document(data, work)
        factory.run_until_wait(work.pk)
        submission = response.submissions.get()
        evidence = data['evidence']['rfp_outcome']
        if key == 'bid-award-walkthrough':
            evidence = add_evidence(operator, case.pk, 'rfp_outcome',
                                    'Synthetic award notice for the exact submitted response. Awarded price NGN 101.25.',
                                    'synthetic:priced-award')
        return {'case': str(case.pk), 'work': work.pk, 'submission': submission.pk,
                'evidence': evidence.pk}
    users = get_user_model().objects
    create_user = users.create_user
    if key == 'changed-milestone':
        with patch.object(test_commercial_changes, 'setup_case', return_value=(operator, case)):
            entry = ChangeImpactTests()
            entry.setUp()
        entry.approved_report()
        return {'case': str(case.pk), 'work': None}
    is_minutes = key in {'minutes', 'outward-minutes', 'minutes-uncertain', 'minutes-selected'}
    entry = FactoryMinutesTests() if is_minutes else FactoryReportingTests()
    with (
        patch.object(document_helpers, 'setup_case', return_value=(operator, case)),
        patch.object(users, 'create_user', side_effect=lambda username: create_user(username=f'state-check-{key}-{username}')),
    ):
        entry.setUp()
    if is_minutes:
        outward = key not in {'minutes', 'minutes-selected'}
        entry.start(outward=outward)
        entry.advance()
        if outward:
            entry.confirm()
            entry.advance()
        if key == 'minutes-uncertain':
            binding = factory_minutes.document(entry.work)
            review_version(operator, case.pk, binding.version_id, 'approve', 'Exact synthetic receipt review', rev(case))
            factory.run_until_wait(entry.work.pk, adapter=InterruptedMinutesDelivery())
            job = PublicationJob.objects.get(publication__factory_work=entry.work)
            if job.status != 'unknown':
                raise ValueError('Expected the original synthetic transmission to remain uncertain')
            return {'case': str(case.pk), 'work': entry.work.pk, 'job': job.pk}
    else:
        artifact(operator, case, 'D05.decision_action_matrix', 'schema:psl/decision-actions/v1',
                 {'rules': [{'role': 'PMO Lead', 'actions': ['return']}]}, entry.owner)
        entry.start_work()
        entry.advance()
        entry.review('return')
    return {'case': str(case.pk), 'work': entry.work.pk}


if (os.environ.get('RAILWAY_ENVIRONMENT_NAME') != 'design-acceptance' or
        os.environ.get('RAILWAY_PROJECT_ID') != 'f957481b-c6f7-43af-bc66-449a330a9d53'):
    raise SystemExit('Exact isolated acceptance environment required')

trial = get_user_model().objects.get(username='psl-agent-trial', is_active=True, is_staff=False, is_superuser=False)
workflow = os.environ.get('PSL_STATE_WALKTHROUGH')
if workflow == 'money-and-bids':
    fixtures = ('known-money', 'bid-loss-walkthrough', 'bid-win-walkthrough', 'delegation-periods', 'delegation-read-only')
elif workflow == 'award-and-money-access':
    fixtures = ('bid-award-walkthrough', 'money-read-only', 'bid-intake-walkthrough', 'corrected-money')
elif workflow == 'portal-and-followup':
    fixtures = ('portal-pricing', 'minutes-selected')
elif workflow == 'message-and-invoice-states':
    fixtures = ('bid-followup-delivery','bid-followup-manual','bid-followup-uncertain',
                'invoice-review','invoice-returned','invoice-owner-needed','invoice-information')
elif workflow == 'stability-states':
    fixtures = ('stability-observations','stability-missing-rule')
elif workflow == 'planning-commercial-issue-states':
    fixtures = ('planning-ready','planning-owner-wait','planning-rules-needed','planning-verified',
                'commercial-review','commercial-information','issue-followup','issue-owner-access','issue-verified')
elif workflow == 'department-input-states':
    fixtures = ('planning-departments','planning-department-rules')
elif workflow == 'go-live-response-states':
    fixtures = ('go-live-client-changes','go-live-client-decline','go-live-client-rules','go-live-client-correction')
elif workflow == 'delivery-recipient-states':
    fixtures = ('handover-review', 'handover-receipt', 'archive-inventory')
elif workflow == 'archive-file-states':
    fixtures = ('archive-file-receipts', 'archive-file-uncertain', 'archive-file-missing')
elif workflow == 'archive-private-store':
    fixtures = ('archive-private-store',)
elif workflow == 'handover-reply-states':
    fixtures = ('handover-external-reply', 'handover-reply-rules', 'handover-reply-gaps')
elif workflow == 'bid-answer-states':
    fixtures = ('bid-answer-review',)
elif workflow == 'costing-proposal-states':
    fixtures = ('costing-proposal-review', 'costing-proposal-own', 'costing-proposal-rules')
else:
    fixtures = ('delegation', 'minutes', 'weekly', 'outward-minutes', 'changed-milestone', 'assistant-draft', 'signed-money', 'minutes-uncertain')
failed = False
for fixture in fixtures:
    try:
        result = prepare(fixture, trial)
        if fixture=='archive-private-store':
            from django.core.exceptions import ValidationError
            from apps.pmo import archive_transfer
            from apps.pmo.models import ArchiveCopyJob
            from apps.workflows import factory_archive
            work=FactoryWork.objects.get(pk=result['work'],case__synthetic=True,
                case__tenant='design-state-walkthrough',case__title='Browser design states · archive-private-store')
            plan=work.file_archives.latest('pk')
            for job in ArchiveCopyJob.objects.filter(file__plan=plan).order_by('pk'):
                if job.status in ['pending','unknown','leased']:
                    archive_transfer.run_once(job.pk,actor=trial)
            files=archive_transfer.projection(trial,work)
            if not files['verified']:
                raise ValidationError('Review the original private-store receipts before continuing this synthetic archive trial.')
            factory.run_until_wait(work.pk)
            work.refresh_from_db()
            proof=factory_archive.verify(work,actor=trial)
            result.update(plan=plan.pk,external_store_bytes_verified=proof['external_bytes_verified'],
                verified_files=files['confirmed'],work_status=work.status)
    except Exception as exc:
        failed = True
        print(f'PSL_STATE_ERROR={fixture}: {type(exc).__name__}: {str(exc)[:240]}', flush=True)
    else:
        print('PSL_STATE_FIXTURE=' + json.dumps({'fixture': fixture, **result}), flush=True)
if failed:
    raise SystemExit(1)
