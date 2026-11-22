import copy
import json
from pathlib import Path

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.documents.models import Publication, PublicationReceipt
from apps.identity.models import Grant
from apps.pmo import delivery, delivery_closure, go_live_replies, issues
from apps.pmo.models import DeliveryRecord, DeliveryDossier, GoLiveClientReply, GoLiveRemediation, GoLiveReplyIssue
from apps.policy.change_drafts import draft_standard_policy
from apps.policy.models import Configuration
from apps.policy.services import active_component, reference_values, transition
from apps.workflows import factory, factory_go_live as go_live
from .helpers import rev
from .test_delivery import DeliveryFixture
from .test_factory_go_live import setup, review, accept


RULES=json.loads(Path('fixtures/go-live-client-replies.json').read_text())['rules']


class GoLiveReplyValidatorTests(SimpleTestCase):
    def test_owner_choices_are_typed_and_required(self):
        from types import SimpleNamespace
        from apps.policy.go_live_reply_validators import SCHEMA, validate_reference

        case = SimpleNamespace(kind='project')
        target = SimpleNamespace(schema_ref=SCHEMA, content=copy.deepcopy(RULES))
        self.assertEqual(validate_reference(target, case), RULES)
        invalid = [
            {'allow_recorder_correction': 'yes'},
            {'recording_roles': []},
            {'channels': ['unreviewed-provider']},
            {'decline_handling': 'assume_accepted'},
            {'issue_states_for_new_release': ['Open']},
        ]
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                target.content = {**copy.deepcopy(RULES), **changes}
                validate_reference(target, case)

    def test_supplied_reply_requires_actual_typed_time_and_attestation(self):
        from adapters.go_live_replies import SuppliedGoLiveReplyAdapter

        for value in [None, '2026-11-17', timezone.now().replace(tzinfo=None)]:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                SuppliedGoLiveReplyAdapter.validate('Sample client', value, 'email', 'Supplied request.', True)
        with self.assertRaises(ValidationError):
            SuppliedGoLiveReplyAdapter.validate('Sample client', timezone.now(), 'email', 'Supplied request.', 'yes')


def configure(f, **changes):
    value=copy.deepcopy(RULES)
    value.update(changes)
    p=draft_standard_policy(f.actor,f.case.pk,go_live_replies.COMPONENT,[value],f.e['policy_decision'].pk,timezone.now())
    transition(f.actor,p.pk,'validated')
    transition(f.actor,p.pk,'active')
    return p


def delivered(base=None, configured=True):
    f=setup(base=base)
    if configured:configure(f)
    factory.run_until_wait(f.work.pk)
    review(f)
    factory.run_until_wait(f.work.pk)
    f.work.refresh_from_db()
    f.version=go_live.document(f.work)
    f.receipt=PublicationReceipt.objects.get(publication__version=f.version)
    return f


def reply(f, outcome='changes_requested', previous=None, role='PM', source=None):
    source=source or f.evidence('client_feedback','Synthetic client response: add the fallback incident contact.')
    note='Synthetic reviewed correction: the preceding response referenced the wrong report.' if outcome=='withdrawn' else 'Synthetic client response: add the fallback incident contact.'
    return go_live_replies.record(f.actor,f.case.pk,f.d.pk,f.receipt.pk,previous.pk if previous else None,
        outcome,'Sample client colleague',timezone.now(),'email',source.pk,
        note,role,True,rev(f.case))


class GoLiveReplyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        f=DeliveryFixture()
        f.setup_delivery()
        f.release()
        cls.base=f

    def test_client_changes_prepare_version_two_with_fresh_review_receipt_and_actual_signatures(self):
        f=delivered(self.base)
        first=f.version
        original_receipt=f.receipt
        source = f.evidence('client_feedback', 'Synthetic client response: add the fallback incident contact.')
        self.client.force_login(f.actor)
        api = f'/api/v1/work/{f.work.pk}/go-live-replies'
        panel = self.client.get(api)
        self.assertEqual(panel.status_code, 200, panel.content)
        self.assertEqual(panel.json()['capture'][0]['receipt_id'], original_receipt.pk)
        submitted = self.client.post(api, {'action': 'record_reply',
            **{key: panel.json()[key] for key in ('expected_revision', 'case_revision')},
            'receipt_id': original_receipt.pk, 'previous_id': None, 'outcome': 'changes_requested',
            'party': 'Sample client colleague', 'responded_at': timezone.now().isoformat(), 'channel': 'email',
            'evidence_id': source.pk, 'note': source.body, 'role': 'PM', 'attested': True}, content_type='application/json')
        self.assertEqual(submitted.status_code, 201, submitted.content)
        response = go_live_replies.current_heads(f.d)[0]
        self.assertEqual(response.pk, submitted.json()['record_id'])
        self.assertEqual(self.client.get(api).json()['replies'][0]['evidence_id'], source.pk)
        with self.assertRaisesMessage(ValidationError,'corrected source versions'):
            accept(f)
        corrected=f.evidence('incident_reporting','Synthetic revised incident plan with the client-requested fallback contact.')
        f.work.refresh_from_db()
        revised = self.client.post(api + '/successor', {'expected_revision': f.work.revision,
            'case_revision': rev(f.case), 'inputs': dict(f.inputs, incident_reporting=corrected.pk),
            'reason': 'Prepare a reviewed successor for the exact supplied client request.'}, content_type='application/json')
        self.assertEqual(revised.status_code, 200, revised.content)
        factory.run_until_wait(f.work.pk)
        f.work.refresh_from_db()
        second=go_live.document(f.work)
        self.assertEqual(second.document_id,first.document_id)
        self.assertEqual(second.number,2)
        self.assertEqual(second.reviews.count(),0)
        self.assertFalse(Publication.objects.filter(version=second).exists())
        self.assertIn(response.note,second.fields['next_steps']['text'])
        self.assertIn(response.evidence_id,second.fields['next_steps']['evidence_ids'])
        self.assertEqual(first.reviews.count(),1)
        review(f)
        factory.run_until_wait(f.work.pk)
        accept(f)
        factory.run_until_wait(f.work.pk)
        f.work.refresh_from_db()
        self.assertEqual(f.work.status,'verified',f.work.finding)
        self.assertEqual(Publication.objects.filter(factory_work=f.work).count(),2)
        self.assertTrue(PublicationReceipt.objects.filter(pk=original_receipt.pk).exists())
        accepted=delivery_closure.accepted_go_live(f.d)
        self.assertEqual(accepted.data['receipt_id'],PublicationReceipt.objects.get(publication__version=second).pk)

    def test_missing_handling_rules_retain_received_facts_and_hold_only_dependent_acceptance(self):
        f=delivered(self.base,configured=False)
        response=reply(f)
        self.assertEqual(response.outcome,'changes_requested')
        metadata=go_live_replies.current_heads(f.d)[0]
        self.assertIn('body',metadata.evidence.get_deferred_fields())
        self.assertIn('payload',metadata.receipt.get_deferred_fields())
        self.assertIn('fields',metadata.receipt.publication.version.get_deferred_fields())
        self.assertTrue(PublicationReceipt.objects.filter(pk=f.receipt.pk).exists())
        with self.assertRaises(ValidationError):
            accept(f)
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='go_live').exists())
        self.client.force_login(f.actor)
        page=self.client.get(reverse('factory_work_response',args=[f.work.pk]))
        self.assertContains(page,'Changes requested')
        self.assertEqual(page.context['row']['state'], 'Client requested changes')
        self.assertNotContains(page, 'D11.adapter_configuration_refs: MISSING')
        self.assertContains(page,'Prepare client response rules for owner review')
        self.assertNotContains(page,'Prepare next report with the agent')
        configure(f)
        with self.assertRaisesMessage(ValidationError,'corrected source versions'):
            go_live_replies.effect(f.d,{key:f.inputs[key] for key in go_live.KINDS})

    def test_decline_moves_through_an_owned_issue_fix_fresh_candidate_gates_and_new_acceptance(self):
        f=delivered(self.base)
        original=f.d
        response=reply(f,'declined')
        with self.assertRaisesMessage(ValidationError,'declined this release'):
            accept(f)
        self.client.force_login(f.actor)
        url=reverse('factory_work_response',args=[f.work.pk])
        api = f'/api/v1/work/{f.work.pk}/go-live-replies/decline'
        choices = self.client.get(api)
        self.assertEqual(choices.status_code, 200, choices.content)
        self.assertEqual(choices.json()['issues'][0]['reply_id'], response.pk)
        self.assertIn(f.actor.pk, {option['id'] for option in choices.json()['issues'][0]['owners']})
        f.work.refresh_from_db()
        self.assertRedirects(self.client.post(url,{'action':'client_decline_issue','revision':f.work.revision,
            'case_revision':rev(f.case),'reply_id':response.pk,'owner_id':f.actor.pk,
            'title':'Synthetic client decline','next_action':'Investigate the exact reported integration failure.',
            'note':'Actual synthetic client response linked to its delivered report.'}),url)
        link=GoLiveReplyIssue.objects.get(reply=response)
        again=go_live_replies.log_problem(f.actor,f.case.pk,response.pk,f.actor.pk,
            'Synthetic client decline','Investigate the exact reported integration failure.',
            'Reuse the original issue relation.',rev(f.case))
        self.assertEqual(again.pk,link.pk)
        f.work.refresh_from_db()
        self.assertRedirects(self.client.post(url,{'action':'client_decline_candidate','revision':f.work.revision,
            'case_revision':rev(f.case),'reply_id':response.pk,'reference':'SAMPLE-REMEDIATED-CANDIDATE',
            'requirements_id':f.e['requirements'].pk,'note':'Prepare a distinct candidate for its own release gates.'}),url)
        successor=DeliveryDossier.objects.get(case=f.case,candidate__reference='SAMPLE-REMEDIATED-CANDIDATE')
        with self.assertRaisesMessage(ValidationError,'reviewed issue-fix handoff'):
            delivery.readiness_inputs(successor)
        proof=f.evidence('go_live_response_correction','Synthetic review of the fixed issue and fresh release candidate.')
        with self.assertRaisesMessage(ValidationError,'Resolve the linked issue'):
            go_live_replies.remediate(f.actor,f.case.pk,response.pk,None,successor.pk,'PMO Lead',proof.pk,
                'Issue work is still outstanding.',rev(f.case))
        issue=link.issue
        state=issue.current
        state=issues.update_issue(f.actor,f.case.pk,issue.pk,state.pk,'manage',response.evidence_id,
            'Synthetic PM severity classification.',rev(f.case),severity='Medium')
        state=issues.update_issue(f.actor,f.case.pk,issue.pk,state.pk,'acknowledge',response.evidence_id,
            'Synthetic responsible owner acknowledgement.',rev(f.case))
        fix=f.evidence('resolution','Synthetic fix and regression evidence for the reported integration failure.')
        state=issues.update_issue(f.actor,f.case.pk,issue.pk,state.pk,'resolve',fix.pk,
            'Synthetic owner records the actual fix evidence.',rev(f.case),fix_id=fix.pk)
        from apps.pmo.gates import register_candidate
        unrelated = register_candidate(f.actor, f.case.pk, 'UNRELATED-CANDIDATE', f.e['requirements'].pk, rev(f.case))
        unrelated_dossier = delivery.open_dossier(f.actor, f.case.pk, unrelated.pk, proof.pk,
            'Independent candidate without the client-decline origin.', rev(f.case))
        available = self.client.get(api)
        self.assertEqual(available.status_code, 200, available.content)
        self.assertEqual([row['id'] for row in available.json()['review_options'][0]['destinations']], [successor.pk])
        with self.assertRaisesMessage(ValidationError, 'exact client decline'):
            go_live_replies.remediate(f.actor, f.case.pk, response.pk, None, unrelated_dossier.pk,
                'PMO Lead', proof.pk, 'An unrelated candidate cannot receive this fix handoff.', rev(f.case))
        f.work.refresh_from_db()
        self.assertRedirects(self.client.post(url,{'action':'client_decline_handoff','revision':f.work.revision,
            'case_revision':rev(f.case),'reply_id':response.pk,'destination_id':successor.pk,'role':'PMO Lead',
            'evidence_id':proof.pk,'note':'The fixed issue may proceed to a distinct candidate with all new release gates.'}),url)
        handoff=GoLiveRemediation.objects.get(reply=response)
        self.assertEqual(handoff.issue_state_id,state.pk)
        self.assertEqual(go_live_replies.projection(f.actor,original)['destinations'][0]['dossier_id'],successor.pk)
        self.assertEqual(go_live_replies.release_handoff(successor)['review_id'],handoff.pk)
        outcome=delivery.latest(original,'release_outcome',False)
        with self.assertRaisesMessage(ValidationError,'already recorded'):
            delivery.capture_release(f.actor,f.case.pk,original.pk,outcome.parent_id,timezone.now(),
                'DISALLOWED-SECOND-RELEASE',fix.pk,'The original candidate cannot be released twice.',rev(f.case))
        f.d=successor
        f.candidate=successor.candidate
        f.kickoff_reference='KICKOFF-REMEDIATED'
        f.release_request_reference='GLPI-REMEDIATED'
        f.release()
        f.inputs={'template_id':f.t.pk,**{key:f.evidence(kind,'Synthetic corrected '+kind+' for the fresh candidate.').pk
            for key,kind in go_live.KINDS.items()}}
        f.work=go_live.start(f.actor,f.case.pk,'GO-LIVE-REMEDIATED',f.d.pk,f.inputs,
            'Go-live after the issue fix and new release gates.',rev(f.case))
        factory.run_until_wait(f.work.pk)
        review(f)
        factory.run_until_wait(f.work.pk)
        accept(f)
        factory.run_until_wait(f.work.pk)
        f.work.refresh_from_db()
        self.assertEqual(f.work.status,'verified',f.work.finding)
        self.assertEqual(DeliveryRecord.objects.filter(dossier=original,kind='go_live').count(),0)
        self.assertEqual(DeliveryRecord.objects.filter(dossier=successor,kind='release_outcome').count(),1)
        self.assertEqual(DeliveryRecord.objects.filter(dossier=successor,kind='go_live').count(),1)
        GoLiveRemediation.objects.create(reply=response,previous=handoff,number=2,destination=successor,
            issue_state=state,configuration=handoff.configuration,evidence=proof,role=handoff.role,
            authority=handoff.authority,note='A raw row supplies no native review event.',actor=f.actor)
        with self.assertRaisesMessage(ValidationError,'native review provenance'):
            go_live_replies.release_handoff(successor)

    def test_reviewed_correction_preserves_the_reply_and_needs_a_fresh_report_review(self):
        f=delivered(self.base)
        response=reply(f,'declined')
        proof=f.evidence('go_live_response_correction','Synthetic independent evidence that the wrong report was referenced.')
        configure(f,allow_recorder_correction=False)
        with self.assertRaises(PermissionDenied):
            reply(f,'withdrawn',response,'PMO Lead',proof)
        self.assertEqual(GoLiveClientReply.objects.count(),1)
        configure(f,allow_recorder_correction=True)
        correction=reply(f,'withdrawn',response,'PMO Lead',proof)
        self.assertEqual(correction.previous_id,response.pk)
        with self.assertRaises(DatabaseError),transaction.atomic():
            GoLiveClientReply.objects.filter(pk=response.pk).update(outcome='withdrawn')
        f.work.refresh_from_db()
        go_live.prepare_client_revision(f.actor,f.work.pk,f.work.revision,rev(f.case),f.inputs,
            'Prepare a fresh reviewed report after the evidenced response correction.')
        factory.run_until_wait(f.work.pk)
        f.work.refresh_from_db()
        self.assertEqual(go_live.document(f.work).number,2)
        review(f)
        factory.run_until_wait(f.work.pk)
        accept(f)
        factory.run_until_wait(f.work.pk)
        f.work.refresh_from_db()
        self.assertEqual(f.work.status,'verified',f.work.finding)
        self.assertEqual(GoLiveClientReply.objects.count(),2)

    def test_restricted_source_is_hidden_from_response_metadata_and_prefilled_forms(self):
        from apps.finance.models import ForecastScenario

        f = delivered(self.base)
        response = reply(f, 'declined')
        ForecastScenario.objects.create(
            case=f.case, reference='SYNTHETIC-PRIVATE-RESPONSE', number=1,
            evidence=response.evidence, payload={'items': []},
            reason='Synthetic source now bound to restricted Finance evidence.', actor=f.actor,
        )
        state = go_live_replies.projection(f.actor, f.d)
        self.assertFalse(state['items'][0]['source_available'])
        self.assertEqual(state['items'][0]['party'], 'Restricted response source')
        self.assertIsNone(state['items'][0]['note'])
        self.client.force_login(f.actor)
        page = self.client.get(reverse('factory_work_response', args=[f.work.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, response.party)
        self.assertNotContains(page, response.note)
        with self.assertRaises(ValidationError):
            go_live_replies.effect(f.d, {key:f.inputs[key] for key in go_live.KINDS})

    def test_http_roles_exact_receipts_draft_rules_and_unavailable_actions(self):
        f=delivered(self.base)
        value=copy.deepcopy(RULES)
        route={'kind':'rfp_submission','key':'preserved','method':'internal_recipient_inbox',
            'destination_ref':'synthetic-existing-route','recipient_ids':[f.actor.pk],'sender_roles':['PM']}
        policy=draft_standard_policy(f.actor,f.case.pk,go_live_replies.COMPONENT,[route,value],f.e['policy_decision'].pk,timezone.now())
        transition(f.actor,policy.pk,'validated')
        transition(f.actor,policy.pk,'active')
        source=f.evidence('client_feedback','Synthetic customer asks for the missing fallback contact.')
        self.client.force_login(f.actor)
        url=reverse('factory_work_response',args=[f.work.pk])
        self.assertContains(self.client.get(url),'Record client response')
        f.work.refresh_from_db()
        data={'action':'client_reply','revision':f.work.revision,'case_revision':rev(f.case),
            'receipt_id':f.receipt.pk,'outcome':'changes_requested','party':'Sample client',
            'responded_at':timezone.now().isoformat(),'channel':'email','evidence_id':source.pk,
            'note':'Add the fallback incident contact.','role':'PM','attested':'on'}
        self.assertRedirects(self.client.post(url,data),url)
        recorded=GoLiveClientReply.objects.get()
        self.assertEqual(recorded.actor_id,f.actor.pk)
        self.assertEqual(recorded.receipt_id,f.receipt.pk)
        self.assertContains(self.client.get(url),'Prepare next report with the agent')
        page = self.client.get(reverse('factory_detail', args=[f.work.pk]))
        self.assertEqual(page.context['row']['state'], 'Client requested changes')
        self.assertEqual(self.client.post(url,{**data,'revision':f.work.revision}).status_code,200)
        self.assertEqual(GoLiveClientReply.objects.count(),1)
        self.assertContains(self.client.post(reverse('factory_invoice_recovery',args=[f.work.pk]),data),'available action')
        f.work.refresh_from_db()
        api = f'/api/v1/work/{f.work.pk}/go-live-replies/decline'
        rules = {key: value for key, value in RULES.items() if key not in {'key', 'kind'}}
        rules['allow_recorder_correction'] = True
        draft_data = {'rules': rules, 'expected_revision': f.work.revision, 'case_revision': rev(f.case),
                      'base_configuration_id': policy.pk, 'evidence_id': f.e['policy_decision'].pk}
        drafted = self.client.post(api, draft_data, content_type='application/json')
        self.assertEqual(drafted.status_code, 201, drafted.content)
        draft=Configuration.objects.filter(case=f.case,component=go_live_replies.COMPONENT).latest('pk')
        self.assertNotEqual(draft.pk,policy.pk)
        self.assertEqual(active_component(go_live_replies.COMPONENT,f.case).pk,policy.pk)
        self.assertIn(route,reference_values(draft))
        Grant.objects.filter(case=f.case,user=f.actor,action='delivery.manage').update(active=False)
        self.assertNotContains(self.client.get(url),'Record client response')
        f.work.refresh_from_db()
        data.update(revision=f.work.revision,case_revision=rev(f.case))
        self.assertEqual(self.client.post(url,data).status_code,403)


class GoLiveReplyConcurrencyTests(TransactionTestCase):
    def test_competing_response_records_do_not_fork_the_exact_receipt(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections,connections
        f=delivered()
        source=f.evidence('client_feedback','Synthetic competing client-response intake.')
        expected=rev(f.case)
        barrier=Barrier(2)

        def record(outcome):
            close_old_connections()
            try:
                barrier.wait(timeout=20)
                row=go_live_replies.record(f.actor,f.case.pk,f.d.pk,f.receipt.pk,None,outcome,
                    'Sample client',timezone.now(),'email',source.pk,'Synthetic recorded response.','PM',True,expected)
                return ('recorded',row.pk)
            except ValidationError:
                return ('stale',None)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            result=list(pool.map(record,['changes_requested','declined']))
        self.assertCountEqual([status for status,_ in result],['recorded','stale'])
        self.assertEqual(GoLiveClientReply.objects.count(),1)
        self.assertEqual(PublicationReceipt.objects.filter(pk=f.receipt.pk).count(),1)
