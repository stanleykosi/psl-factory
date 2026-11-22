"""Selected F12/F13 native factory, with explicitly synthetic financial rules."""
import copy,json
from datetime import timedelta
from django.test import TestCase,Client
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import connection,transaction,DatabaseError
from django.urls import reverse
from django.utils import timezone
from apps.identity.models import Grant
from apps.finance import schedules,analysis
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import transition
from apps.workflows import factory,factory_schedules as flow
from apps.workflows.models import FactoryWork
from .schedule_helpers import fixture,policy,evidence,row,review,accepted_equity
from .helpers import check_investigation_progress, rev

class FactorySchedulesTests(TestCase):
    def setUp(self):
        self.f=fixture();f=self.f
        value={'definition':flow.DEFINITION,'max_steps':40,'max_tokens':50000,'tokens_per_call':100,'max_children':100,'max_depth':3,'lease_seconds':30,'max_age_seconds':86400,'required_evidence_kinds':[flow.KIND],'information_resolver_id':None,'executor_id':None,'review_role':None,'provider':'synthetic_factory_v1','enabled':True}
        p=draft_operator_policy(f['actor'],f['case'].pk,'OPS.factory_schedules_execution',value,f['e']['policy_decision'].pk,timezone.now()-timedelta(seconds=1));transition(f['actor'],p.pk,'validated');transition(f['actor'],p.pk,'active')
        self.payload=copy.deepcopy(f['values']['detail']);self.payload['rows']=[row(f,'a','-600'),row(f,'b','-400')]
    def start(self,inventory=False,accepted=False):
        f=self.f
        if inventory:
            body=accepted_equity(f) if accepted else f['values']['inventory'];e=evidence(f,'schedule_inventory',json.dumps(body))
            self.args=['inventory',None,e.pk,None]
        else:self.args=['income',f['parent'].pk,f['e']['income_detail'].pk,self.payload]
        self.work=flow.start(f['actor'],f['case'].pk,'SCHEDULES-1',*self.args,'factory-schedules',rev(f['case']));return self.work
    def advance(self):factory.run_until_wait(self.work.pk);self.work.refresh_from_db();return self.work
    def rows(self):
        with connection.cursor() as c:
            c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename");names=[r[0] for r in c.fetchall()];result={}
            for n in names:c.execute('SELECT to_jsonb(t)::text FROM '+connection.ops.quote_name(n)+' t ORDER BY to_jsonb(t)::text');result[n]=c.fetchall()
            return result

    def test_start_uses_selected_income_and_inventory_evidence_without_json_override(self):
        f = self.f
        income_source = evidence(f, 'income_detail', json.dumps(self.payload))
        inventory_source = evidence(f, 'schedule_inventory', json.dumps(f['values']['inventory']))
        self.client.force_login(f['actor'])
        url = reverse('factory_create') + '?definition=' + flow.DEFINITION + '&case=' + str(f['case'].pk)
        page = self.client.get(url)
        self.assertContains(page, 'Leave this blank to use the exact selected evidence.')
        self.assertNotContains(page, '>null</textarea>')
        for kind, source, parent in [('income', income_source, f['parent'].pk), ('inventory', inventory_source, '')]:
            with self.subTest(kind=kind):
                values = {'definition': flow.DEFINITION, 'case': f['case'].pk, 'key': f'drawer-{kind}', 'kind': kind,
                          'reference': f'sample-{kind}', 'revision': rev(f['case']), 'parent_id': parent,
                          'evidence_id': source.pk, 'payload': ''}
                response = self.client.post(url, values)
                self.assertEqual(response.status_code, 302, response.context and response.context['form'].errors)
                self.work = FactoryWork.objects.get(key=f'drawer-{kind}')
                self.advance()
                schedule = flow.schedule(self.work)
                self.assertIsNotNone(schedule, self.work.finding)
                self.assertEqual(schedule.evidence_id, source.pk)
                self.assertFalse(schedule.reviews.exists())
                if kind == 'income':
                    self.assertEqual(schedule.result['adjusted_total'], '-1000')
                else:
                    self.assertFalse(schedule.result['complete_inventory'])
    def test_income_native_chain_and_read_only_metadata(self):
        f=self.f;self.start()
        check_investigation_progress(self, f['actor'], self.work, 'Investigating the selected income and schedule evidence.')
        self.advance();s=flow.schedule(self.work);self.assertIsNotNone(s,self.work.finding);self.assertEqual(s.result['adjusted_total'],'-1000');self.assertNotEqual(self.work.status,'verified')
        review(f,s);self.advance();self.assertEqual(self.work.status,'verified',self.work.finding);self.assertFalse(flow.verify(self.work,f['actor'])['ledger_posted'])
        self.client.force_login(f['reviewer']);Grant.objects.filter(case=f['case'],user=f['reviewer'],action='schedules.report').update(active=False)
        before=self.rows();response=self.client.get('/work/'+str(self.work.pk)+'/');self.assertContains(response,'Private report values require separate report permission');self.assertEqual(before,self.rows());self.assertNotContains(response,'-600');self.assertNotContains(response,'-400');self.assertFalse(flow.projection(f['reviewer'],self.work)['readiness_changed'])
        self.assertEqual(self.client.get('/cases/'+str(f['case'].pk)+'/finance/schedules/'+str(s.pk)+'/report/').status_code,403)
        self.assertEqual(flow.start(f['actor'],f['case'].pk,'SCHEDULES-1',*self.args,'factory-schedules',rev(f['case'])).pk,self.work.pk)
        review(f,s,'revoke')
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
    def test_partial_inventory_is_only_selected_dependency_output(self):
        f=self.f;self.start(inventory=True);self.advance();s=flow.schedule(self.work);self.assertIsNotNone(s,self.work.finding);self.assertFalse(s.result['complete_inventory']);review(f,s);self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        proof=flow.verify(self.work,f['actor']);self.assertEqual(proof['verification_scope'],'selected_supplied_schedule_dependency_inventory');self.assertFalse(proof['native_workbook_verified']);self.assertFalse(proof['complete_inventory'])

    def test_schedule_decisions_and_corrected_source_wake_the_existing_background_request(self):
        from apps.workflows import factory_progress

        f = self.f
        self.start()
        job = factory_progress.set_progress(f['actor'], self.work.pk, self.work.revision, True)

        def drain_to(status):
            for _ in range(15):
                self.assertEqual(factory_progress.run_once(), job.pk)
                job.refresh_from_db()
                if job.status != 'queued':
                    break
            self.assertEqual(job.status, status, self.work.finding)
            self.work.refresh_from_db()

        def assert_woken():
            job.refresh_from_db()
            self.assertEqual(job.requested_by_id, f['actor'].pk)
            self.assertLessEqual(job.available_at, timezone.now())
            self.assertEqual(job.observation, '')

        decision = reverse('factory_invoice_decision', args=[self.work.pk])
        recovery = reverse('factory_invoice_recovery', args=[self.work.pk])

        def submit_review(schedule, verdict):
            return self.client.post(decision, {
                'action': 'review', 'revision': self.work.revision, 'case_revision': rev(f['case']),
                'target': schedule.pk, 'verdict': verdict, 'evidence': f['e']['finance_review'].pk,
                'note': 'Synthetic exact schedule decision for the current evidence.',
            })

        drain_to('waiting')
        original = flow.schedule(self.work)
        self.assertIsNotNone(original)
        self.assertGreater(job.available_at, timezone.now())
        self.assertTrue(job.observation)
        before = (job.available_at, job.observation, job.updated_at)
        self.client.force_login(f['actor'])
        self.assertEqual(submit_review(original, 'approve').status_code, 403)
        job.refresh_from_db()
        self.assertEqual((job.available_at, job.observation, job.updated_at), before)
        self.assertFalse(original.reviews.exists())

        self.client.force_login(f['reviewer'])
        self.assertRedirects(submit_review(original, 'return'), decision, fetch_redirect_response=False)
        assert_woken()
        drain_to('waiting')
        self.assertEqual(original.reviews.get().verdict, 'return')

        corrected = dict(self.payload, rows=[row(f, 'corrected', '-1000')])
        replacement = evidence(f, 'income_detail', json.dumps(corrected))
        self.client.force_login(f['actor'])
        response = self.client.post(recovery, {
            'action': 'correct', 'revision': self.work.revision, 'case_revision': rev(f['case']),
            'kind': 'income', 'parent_id': f['parent'].pk, 'evidence_id': replacement.pk, 'payload': '',
            'reason': 'The replacement file contains the corrected synthetic breakdown.',
        })
        self.assertRedirects(response, recovery, fetch_redirect_response=False)
        assert_woken()
        drain_to('waiting')
        successor = flow.schedule(self.work)
        self.assertIsNotNone(successor)
        self.assertNotEqual(successor.pk, original.pk)
        self.assertEqual(successor.evidence_id, replacement.pk)

        self.client.force_login(f['reviewer'])
        self.assertRedirects(submit_review(successor, 'approve'), decision, fetch_redirect_response=False)
        assert_woken()
        with self.assertRaisesMessage(DatabaseError, 'Observed exact current human-reviewed selected schedule required'):
            with transaction.atomic():
                FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
        drain_to('finished')
        self.assertEqual(self.work.status, 'verified', self.work.finding)
        self.assertEqual(flow.verify(self.work, f['actor'])['schedule_review'], successor.reviews.get().pk)
        self.assertEqual(original.reviews.get().verdict, 'return')
    def test_af13_accepted_inventory_and_source_supersession(self):
        from apps.documents import validation as v
        f=self.f;self.start(inventory=True,accepted=True);self.advance();s=flow.schedule(self.work);self.assertIsNotNone(s,self.work.finding);review(f,s);self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        old=f['discovery_source'];v.capture_source(f['actor'],f['case'].pk,old.reference,old.evidence_id,old.metadata,rev(f['case']))
        with self.assertRaises((ValidationError,PermissionDenied)):flow.verify(self.work,f['actor'])
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')

    def test_returned_income_row_requires_explicit_treatment_and_fresh_exact_review(self):
        from apps.core.models import Audit
        from apps.workflows import factory_progress

        f = self.f
        selected = dict(row(f, 'reviewed-timing-difference', '0'), duplicate_state='separately_justified')
        self.payload['rows'].append(selected)
        self.start()
        self.advance()
        original = flow.schedule(self.work)
        url = reverse('factory_invoice_recovery', args=[self.work.pk])
        self.client.force_login(f['actor'])
        self.assertNotContains(self.client.get(url), 'Row relationship')
        original_return = flow.review(f['reviewer'], self.work.pk, self.work.revision, rev(f['case']), original.pk,
                                      'return', f['e']['finance_review'].pk, 'Review the timing difference relationship.')
        self.work.refresh_from_db()
        values = {'action': 'resubmit_returned_row', 'target': original.pk, 'return_id': original_return.pk,
                  'row_key': selected['key'], 'revision': self.work.revision, 'case_revision': rev(f['case'])}
        before = self.work.source_head_id

        self.client.force_login(f['reviewer'])
        self.assertNotContains(self.client.get(url), 'Row relationship')
        with self.assertRaises(PermissionDenied):
            flow.resubmit_returned_row(f['reviewer'], self.work.pk, self.work.revision, rev(f['case']), original.pk,
                                       original_return.pk, selected['key'], 'reclassification')

        self.client.force_login(f['actor'])
        response = self.client.get(url)
        self.assertContains(response, 'Review the timing difference relationship.')
        self.assertContains(response, 'schedule-correction-drawer')
        self.assertContains(response, 'Select corrected sources and rebuild')
        relationship = response.context['correction_form']['relationship']
        self.assertIsNone(relationship.value())
        self.assertNotIn('checked', str(relationship))
        self.assertEqual([choice for choice, _ in relationship.field.choices],
                         ['disaggregation', 'reclassification', 'additive'])
        invalid = (
            values,
            dict(values, relationship='disaggregation'),
            dict(values, relationship='reclassification', target=original.pk + 1),
            dict(values, relationship='reclassification', return_id=original_return.pk + 1),
            dict(values, relationship='reclassification', case_revision=rev(f['case']) - 1),
            dict(values, relationship=['additive', 'reclassification']),
            dict(values, relationship='reclassification', row_key='another-row'),
        )
        for command in invalid:
            with self.subTest(command=command):
                self.assertContains(self.client.post(url, command), 'errorlist')
                self.work.refresh_from_db()
                self.assertEqual(self.work.source_head_id, before)
        command = dict(values, relationship='reclassification')
        self.assertRedirects(self.client.post(url, command), url, fetch_redirect_response=False)
        self.assertNotEqual(self.client.post(url, command).status_code, 302)

        job = self.work.background_progress

        def drain_progress(target_status):
            for _ in range(15):
                self.assertEqual(factory_progress.run_once(), job.pk)
                job.refresh_from_db()
                if job.status != 'queued':
                    break
            self.assertEqual(job.status, target_status, job.observation)
            self.work.refresh_from_db()

        drain_progress('waiting')
        successor = flow.schedule(self.work)
        self.assertIsNotNone(successor)
        self.assertEqual(successor.version, original.version + 1)
        self.assertEqual((successor.parent_id, successor.evidence_id), (original.parent_id, original.evidence_id))
        self.assertEqual(successor.payload['rows'], original.payload['rows'][:-1] + [dict(selected, relationship='reclassification')])
        self.assertEqual(original.reviews.get().pk, original_return.pk)
        self.assertFalse(successor.reviews.exists())
        self.assertNotEqual(self.work.status, 'verified')
        audit = Audit.objects.get(case=f['case'], action='finance.schedule_returned_row_corrected')
        self.assertEqual(audit.data['return_review'], original_return.pk)
        self.assertEqual(audit.data['current_source'], self.work.source_head_id)
        approved = flow.review(f['reviewer'], self.work.pk, self.work.revision, rev(f['case']), successor.pk,
                               'approve', f['e']['finance_review'].pk, 'Independent decision on the new exact version.')
        drain_progress('finished')
        self.assertEqual(flow.verify(self.work, f['actor'])['schedule_review'], approved.pk)
    def test_current_review_wait_is_not_rebuild_and_is_in_decision_queue(self):
        f=self.f;self.start();self.advance();s=flow.schedule(self.work)
        with self.assertRaises(ValidationError):flow.correct(f['actor'],self.work.pk,self.work.revision,rev(f['case']),*self.args,'Do not bypass the exact pending review')
        self.client.force_login(f['reviewer'])
        for q in ['needs_me','decisions']:self.assertContains(self.client.get('/?queue='+q),'factory-schedules')
        from apps.policy.schedule_validators import INCOME
        policy(f,INCOME,f['values']['income_rule']);self.assertFalse(flow.projection(f['reviewer'],self.work)['pending_reviews'])
        flow.correct(f['actor'],self.work.pk,self.work.revision,rev(f['case']),*self.args,'Rebuild with the newly configured rule');self.advance();self.assertNotEqual(flow.schedule(self.work).pk,s.pk)

    def test_duplicate_additions_use_exact_held_rows_and_prepare_an_independent_review(self):
        from django.urls import reverse
        from apps.core.models import Audit
        from apps.workflows import factory_progress

        f = self.f
        first = dict(row(f, 'already-captured', '20', 'additive'), duplicate_state='not_assessed')
        second = dict(row(f, 'separate-charge', '15', 'additive'), duplicate_state='not_assessed')
        self.payload['rows'].extend([first, second])
        self.start()
        self.advance()
        held = flow.schedule(self.work)
        self.assertEqual(held.result['status'], 'held')
        target = reverse('factory_invoice_recovery', args=[self.work.pk])
        self.client.force_login(f['actor'])
        page = self.client.get(target)
        self.assertContains(page, 'Resolve possible duplicate additions')
        self.assertContains(page, 'Duplicate check for already-captured')
        self.assertContains(page, 'Duplicate check for separate-charge')
        values = {'action': 'resolve_duplicates', 'revision': self.work.revision, 'case_revision': rev(f['case']),
                  'target': held.pk, 'evidence': f['e']['finance_review'].pk, 'treatment_0': 'already_represented',
                  'reason': 'Synthetic proof distinguishes an existing amount from an evidenced addition.'}
        self.assertContains(self.client.post(target, values), 'choose a treatment for every shown addition')
        self.assertFalse(Audit.objects.filter(case=f['case'], action='finance.schedule_duplicates_resolved').exists())
        values['treatment_1'] = 'separately_justified'
        self.assertRedirects(self.client.post(target, values), target, fetch_redirect_response=False)
        self.assertFalse(held.reviews.exists())
        self.assertEqual([r['duplicate_state'] for r in held.payload['rows'][2:]], ['not_assessed', 'not_assessed'])
        self.assertEqual(Audit.objects.get(case=f['case'], action='finance.schedule_duplicates_resolved').data['previous_schedule'], held.pk)
        request = self.work.background_progress
        self.assertEqual(request.status, 'queued')
        for _ in range(15):
            factory_progress.run_once()
            self.work.refresh_from_db()
            prepared = flow.schedule(self.work)
            if prepared and prepared.result['status'] == 'ready':
                break
        self.assertEqual(prepared.result['adjusted_total'], '-985')
        self.assertEqual([r['key'] for r in prepared.payload['rows']], ['a', 'b', 'separate-charge'])
        self.assertFalse(prepared.reviews.exists())
        self.assertNotEqual(self.work.status, 'verified')
        preview = self.client.get(reverse('factory_detail', args=[self.work.pk]))
        self.assertContains(preview, 'Prepared total')
        self.assertContains(preview, '-985')
        self.assertNotContains(preview, 'Open exact reviewed report')
        review(f, prepared)
        self.advance()
        self.assertEqual(self.work.status, 'verified')
    def test_exact_export_reconciles_and_requires_separate_native_adjustment_review(self):
        f=self.f;self.payload['rows']=[row(f,'supplement','20','additive',lines=[{'account':'sales','amount':'20'}])];self.start();self.advance();s=flow.schedule(self.work);review(f,s);self.advance()
        args=[f['actor'],self.work.pk,self.work.revision,rev(f['case']),s.pk,'additive',f['e']['finance_adjustment'].pk];a=flow.export(*args);args[3]=rev(f['case']);self.assertEqual(flow.export(*args).pk,a.pk)
        with self.assertRaises(ValidationError):analysis.map_source(f['actor'],f['case'].pk,f['source'].pk,[a.adjustment_id],rev(f['case']))
        analysis.review(f['reviewer'],f['case'].pk,'adjustment',a.adjustment_id,'Finance','approve',f['e']['finance_review'].pk,'Separate reporting adjustment approval',rev(f['case']));mapped=analysis.map_source(f['actor'],f['case'].pk,f['source'].pk,[a.adjustment_id],rev(f['case']));self.assertFalse(mapped.result['ledger_posted'])

    def test_api_schedule_duplicate_correction_review_and_adjustment_handoff(self):
        f = self.f
        self.payload['rows'] = [dict(row(f, 'supplement', '20', 'additive',
                                         lines=[{'account': 'sales', 'amount': '20'}]),
                                     duplicate_state='not_assessed')]
        self.start()
        self.advance()
        held = flow.schedule(self.work)
        url = f'/api/v1/work/{self.work.pk}/finance-schedule'
        review_url = f'/api/v1/work/{self.work.pk}/reviews'
        self.client.force_login(f['actor'])

        def post(target, values):
            return self.client.post(target, values, content_type='application/json')

        def read():
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, response.content)
            return response.json()

        def revisions(view):
            return {key: view[key] for key in ('expected_revision', 'case_revision')}

        page = read()
        self.assertEqual(page['duplicates'], ['supplement'])
        self.assertEqual(page['result']['status'], 'held')
        self.assertFalse(page['can_export'])
        changes = {**revisions(page), 'action': 'resolve_duplicates', 'schedule_id': held.pk,
                   'decisions': [{'key': 'supplement', 'treatment': 'separately_justified'}],
                   'evidence_id': f['e']['finance_review'].pk, 'reason': 'Synthetic evidence supports a distinct amount.'}
        self.assertNotEqual(post(url, dict(changes, schedule_id=held.pk + 1)).status_code, 201)
        self.assertEqual(post(url, changes).status_code, 201)
        self.advance()
        page = read()
        self.assertNotEqual(page['schedule_id'], held.pk)
        self.assertEqual(page['result']['adjusted_total'], '-980')
        verdict = {**revisions(page), 'kind': 'schedule', 'target_id': page['schedule_id'], 'verdict': 'approve',
                   'evidence_id': f['e']['finance_review'].pk, 'note': 'Independent review of the corrected schedule.'}
        self.assertEqual(post(review_url, verdict).status_code, 403)
        self.client.force_login(f['reviewer'])
        self.assertIn('approve', read()['review_verdicts'])
        approval = post(review_url, verdict)
        self.assertEqual(approval.status_code, 200, approval.content)
        self.advance()
        self.client.force_login(f['actor'])
        approved = read()
        self.assertTrue(approved['can_export'])
        export = post(url, {**revisions(approved), 'action': 'export_adjustment',
                            'schedule_id': approved['schedule_id'], 'kind': 'additive',
                            'evidence_id': f['e']['finance_adjustment'].pk})
        self.assertEqual(export.status_code, 201, export.content)
        recorded = read()['exports'][0]
        self.assertEqual(recorded['id'], export.json()['record_id'])
        self.assertFalse(held.reviews.exists())
        finance = f"/api/v1/projects/{f['case'].pk}"
        adjustment_url = f"{finance}/accounting-adjustments/{recorded['adjustment_id']}"
        mapping_url = f"{finance}/accounting-sources/{f['source'].pk}/mappings"
        adjustment = self.client.get(adjustment_url)
        self.assertEqual(adjustment.status_code, 200, adjustment.content)
        self.assertIsNone(adjustment.json()['review_id'])
        mapping = {'case_revision': adjustment.json()['case_revision'], 'adjustment_ids': [recorded['adjustment_id']]}
        self.assertNotEqual(post(mapping_url, mapping).status_code, 201)
        self.client.force_login(f['reviewer'])
        decision = post(adjustment_url, {'case_revision': rev(f['case']), 'role': 'Finance', 'verdict': 'approve',
                                         'evidence_id': f['e']['finance_review'].pk, 'note': 'Separate adjustment review.'})
        self.assertEqual(decision.status_code, 201, decision.content)
        self.client.force_login(f['actor'])
        mapped = post(mapping_url, dict(mapping, case_revision=rev(f['case'])))
        self.assertEqual(mapped.status_code, 201, mapped.content)
        note = self.client.get(f"{finance}/accounting-mappings/{mapped.json()['id']}")
        self.assertEqual(note.status_code, 200, note.content)
        self.assertIn(f"adjustment:{recorded['adjustment_id']}:1", [item['source_line'] for item in note.json()['rows']])
        self.assertFalse(note.json()['ledger_posted'])
        Grant.objects.filter(case=f['case'], user=f['actor'], action='schedules.report').update(active=False)
        redacted = read()
        self.assertIsNone(redacted['result'])
        self.assertIsNone(redacted['income'])
        self.assertEqual(redacted['exports'], [])

    def test_api_schedule_return_preparer_correction_and_inventory_selection(self):
        f = self.f
        self.payload['rows'].append(dict(row(f, 'timing', '0'), duplicate_state='separately_justified'))
        self.start()
        self.advance()
        original = flow.schedule(self.work)
        returned = flow.review(f['reviewer'], self.work.pk, self.work.revision, rev(f['case']), original.pk,
                               'return', f['e']['finance_review'].pk, 'Confirm the timing relationship.')
        url = f'/api/v1/work/{self.work.pk}/finance-schedule'
        self.client.force_login(f['actor'])
        current = self.client.get(url).json()
        self.assertEqual(current['returned']['review_id'], returned.pk)
        self.assertIsNone(current['result'])
        change = {'action': 'resubmit_row', 'expected_revision': current['expected_revision'],
                  'case_revision': current['case_revision'], 'schedule_id': original.pk,
                  'return_id': returned.pk, 'row_key': 'timing', 'relationship': 'reclassification'}
        self.client.force_login(f['reviewer'])
        self.assertIsNone(self.client.get(url).json()['returned'])
        self.assertEqual(self.client.post(url, change, content_type='application/json').status_code, 403)
        self.client.force_login(f['actor'])
        updated = self.client.post(url, change, content_type='application/json')
        self.assertEqual(updated.status_code, 201, updated.content)
        self.advance()
        current = self.client.get(url).json()
        self.assertNotEqual(current['schedule_id'], original.pk)
        self.assertEqual(current['stage'], 'output_review')
        self.assertIsNone(current['review_id'])

        supplied = evidence(f, 'schedule_inventory', json.dumps(f['values']['inventory']))
        selected = flow.start(f['actor'], f['case'].pk, 'INVENTORY-2', 'inventory', None, supplied.pk,
                              None, 'selected-inventory', rev(f['case']))
        factory.run_until_wait(selected.pk)
        response = self.client.get(f'/api/v1/work/{selected.pk}/finance-schedule')
        self.assertEqual(response.status_code, 200, response.content)
        inventory = response.json()
        self.assertEqual(inventory['inventory'], f['values']['inventory'])
        self.assertEqual(inventory['result']['coverage'], 'partial')
        self.assertFalse(inventory['result']['complete_inventory'])
        self.assertIsNone(inventory['result']['adjusted_total'])

    def test_cancel_restart_forgery_and_source_scope(self):
        f=self.f;self.start();self.client.force_login(f['actor']);url='/work/'+str(self.work.pk)+'/'
        self.client.post(url,{'action':'advance','revision':self.work.revision,'approved_by':'Finance'});self.assertIsNone(flow.schedule(self.work))
        factory.manage(f['actor'],self.work.pk,self.work.revision,'cancel');self.advance();self.assertEqual(self.work.status,'cancelled');flow.restart(f['actor'],self.work.pk,self.work.revision,rev(f['case']),'Fresh human restart instruction');self.advance();self.assertIsNotNone(flow.schedule(self.work),self.work.finding)
        Grant.objects.filter(case=f['case'],user=f['actor'],action='finance.read').update(active=False);self.assertEqual(self.client.get(url).status_code,404)
    def test_http_intake_review_and_csrf_preserve_native_authority(self):
        from django.urls import reverse
        f=self.f;self.client.force_login(f['actor']);url=reverse('factory_create')+'?definition='+flow.DEFINITION+'&case='+str(f['case'].pk)
        before=self.rows();self.assertEqual(self.client.get(url).status_code,200);self.assertEqual(before,self.rows())
        response=self.client.post(reverse('factory_create'),{'definition':flow.DEFINITION,'key':'SCHEDULES-HTTP','case':f['case'].pk,'reference':'http-schedules','revision':rev(f['case']),'kind':'income','parent_id':f['parent'].pk,'evidence_id':f['e']['income_detail'].pk,'payload':json.dumps(self.payload)})
        self.assertEqual(response.status_code,302);self.work=FactoryWork.objects.get(key='SCHEDULES-HTTP');self.advance();s=flow.schedule(self.work);self.assertIsNotNone(s,self.work.finding)
        url=reverse('factory_detail',args=[self.work.pk]);secure=Client(enforce_csrf_checks=True);secure.force_login(f['reviewer']);self.assertEqual(secure.post(url,{'action':'review'}).status_code,403)
        self.client.force_login(f['reviewer']);response=self.client.post(url,{'action':'review','revision':self.work.revision,'case_revision':rev(f['case']),'target':s.pk,'verdict':'approve','evidence':f['e']['finance_review'].pk,'note':'Exact synthetic human review through primary console'})
        self.assertEqual(response.status_code,302);self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
    def test_focused_schedule_return_correction_and_withdrawal_keep_exact_versions(self):
        from django.urls import reverse

        f=self.f;self.start();self.advance();original=flow.schedule(self.work)
        decision=reverse('factory_invoice_decision', args=[self.work.pk])
        recovery=reverse('factory_invoice_recovery', args=[self.work.pk])
        self.client.force_login(f['reviewer'])
        self.assertContains(self.client.get(decision), 'Approve exact schedule')
        exceptions = reverse('home') + '?queue=exceptions&q=' + self.work.key
        self.assertNotIn(self.work.pk, [row['work'].pk for row in self.client.get(exceptions).context['rows']])
        response=self.client.post(decision, {'action':'review','revision':self.work.revision,'case_revision':rev(f['case']),
            'target':original.pk,'verdict':'return','evidence':f['e']['finance_review'].pk,'note':'Correct the source breakdown'})
        self.assertRedirects(response, decision, fetch_redirect_response=False)
        page=self.client.get(decision)
        self.assertContains(page, 'Returned for correction')
        self.assertNotContains(page, 'Approve exact schedule')
        Grant.objects.filter(case=f['case'], user=f['reviewer'], action='factory.manage').update(active=False)
        self.assertContains(self.client.get(exceptions), 'Returned for correction')
        self.assertNotContains(self.client.get(recovery), 'Correct and resubmit')
        with self.assertRaisesMessage(ValidationError, 'Prepare a corrected schedule version'):
            review(f,original)
        self.client.force_login(f['actor'])
        fixed=copy.deepcopy(self.payload);fixed['rows']=[row(f,'corrected','-1000')]
        response=self.client.post(recovery, {'action':'correct','revision':self.work.revision,'case_revision':rev(f['case']),
            'kind':'income','parent_id':f['parent'].pk,'evidence_id':f['e']['income_detail'].pk,
            'payload':json.dumps(fixed),'reason':'Reviewed corrected income detail'})
        self.assertRedirects(response, recovery, fetch_redirect_response=False)
        self.advance();successor=flow.schedule(self.work)
        self.assertNotEqual(successor.pk, original.pk)
        review(f,successor);self.advance()
        self.assertEqual(self.work.status, 'verified')
        review(f,successor,'revoke')
        self.client.force_login(f['reviewer'])
        page=self.client.get(decision)
        self.assertContains(page, 'Approval withdrawn')
        self.assertContains(page, 'Restore exact approval')
        self.assertNotContains(page, 'Approve exact schedule')
        self.assertEqual(original.reviews.get().verdict, 'return')
    def test_af13_grant_withdrawal_invalidates_native_and_sql_without_private_report_grant(self):
        f=self.f;self.start(inventory=True,accepted=True);self.advance();s=flow.schedule(self.work);review(f,s);self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        Grant.objects.filter(case=f['case'],user=f['reviewer'],action='validation.accept').update(active=False)
        with self.assertRaises((ValidationError,PermissionDenied)):flow.verify(self.work,f['actor'])
        self.assertFalse(flow.projection(f['reviewer'],self.work)['pending_reviews'])
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
    def test_scoped_sql_currentness_tracks_native_grants_context_and_wall_time(self):
        import time
        from tests.test_policy_scopes import fixture as scope_fixture,source_version
        from apps.policy import scopes
        from apps.policy.services import resolve
        from .helpers import envelope
        a,source,target,se,te=scope_fixture()
        src=source_version(a,source,se);cfg=scopes.apply(a,src.pk,target.pk,te.pk,[]);transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
        def current():
            with connection.cursor() as c:c.execute('SELECT psl_schedules_policy_current(%s,%s)',[str(target.pk),cfg.pk]);return c.fetchone()[0]
        self.assertTrue(current());self.assertEqual(resolve(cfg.component,target).status,'ACTIVE')
        Grant.objects.filter(case=source,user=a,action='policy.activate').update(active=False);self.assertFalse(current());self.assertNotEqual(resolve(cfg.component,target).status,'ACTIVE')
        Grant.objects.filter(case=source,user=a,action='policy.activate').update(active=True);self.assertTrue(current())
        target.tenant='changed-scope';target.save(update_fields=['tenant']);self.assertFalse(current());self.assertNotEqual(resolve(cfg.component,target).status,'ACTIVE')
        target.tenant=source.tenant;target.save(update_fields=['tenant']);self.assertTrue(current())
        scopes.transition(a,src.pk,'revoked');self.assertFalse(current());self.assertEqual(resolve(cfg.component,target).status,'REVOKED')
        env=envelope(source,'D04.iana_timezone','UTC',se);env['effective_until']=(timezone.now()+timedelta(seconds=4)).isoformat();src=source_version(a,source,se,env=env);cfg=scopes.apply(a,src.pk,target.pk,te.pk,[]);transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
        self.assertTrue(current());time.sleep(max(0,(timezone.datetime.fromisoformat(env['effective_until'])-timezone.now()).total_seconds())+0.1)
        self.assertEqual(resolve(cfg.component,target).status,'EXPIRED');self.assertFalse(current())
    def test_inactive_unused_authority_assignee_holds_native_and_sql(self):
        from django.contrib.auth import get_user_model
        from apps.policy.schedule_validators import AUTH
        f=self.f;extra=get_user_model().objects.create_user(username='unused-schedule-authority');rules=copy.deepcopy(f['values']['authority']);rules['assignments'].append({'user_id':extra.pk,'role':'Finance','purposes':['income']});policy(f,AUTH,rules)
        self.start();self.advance();s=flow.schedule(self.work);review(f,s);self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        extra.is_active=False;extra.save(update_fields=['is_active'])
        with self.assertRaises((ValidationError,PermissionDenied)):flow.verify(self.work,f['actor'])
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
    def test_selected_inventory_retains_unconfigured_af13_domain_gap(self):
        from apps.documents import validation as v
        from apps.policy.services import resolve
        f=self.f;body=accepted_equity(f);p=f['package'];payload=copy.deepcopy(p.payload)
        component='D09.support_sop_ref';self.assertEqual(resolve(component,f['case']).status,'MISSING');payload['policy_components']=[component]
        package=v.prepare_package(f['actor'],f['case'].pk,p.reference,payload,f['e']['policy_decision'].pk,rev(f['case']));body['schedules'][0]['validation_package_id']=package.pk
        e=evidence(f,'schedule_inventory',json.dumps(body));self.args=['inventory',None,e.pk,None]
        self.work=flow.start(f['actor'],f['case'].pk,'SCHEDULES-1',*self.args,'factory-schedules',rev(f['case']));self.advance();s=flow.schedule(self.work);self.assertIsNotNone(s,self.work.finding);self.assertFalse(s.result['complete_inventory']);review(f,s);self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
    def test_nonactive_domain_pins_follow_native_scope_context_and_grants(self):
        import time
        from tests.test_policy_scopes import fixture as scope_fixture,source_version
        from apps.policy import scopes
        from apps.policy.services import resolve,save_draft
        from .helpers import envelope
        a,source,target,se,te=scope_fixture();key='D04.iana_timezone'
        def pin(status):
            with connection.cursor() as cursor:
                cursor.execute('SELECT psl_schedules_policy_pin_current(%s,%s,%s::jsonb)',[str(target.pk),key,json.dumps({'status':status,'id':None})]);return cursor.fetchone()[0]
        self.assertEqual(resolve(key,target).status,'MISSING');self.assertTrue(pin('MISSING'))
        env=envelope(target,key,'UTC',te);env['effective_from']=(timezone.now()+timedelta(hours=1)).isoformat()
        cfg=save_draft(a,target.pk,env);transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
        self.assertEqual(resolve(key,target).status,'MISSING');self.assertTrue(pin('MISSING'))
        target.synthetic=False;target.save(update_fields=['synthetic'])
        self.assertEqual(resolve(key,target).status,'INVALID');self.assertFalse(pin('MISSING'))
        target.synthetic=True;target.save(update_fields=['synthetic'])
        env=envelope(source,key,'UTC',se);env['effective_until']=(timezone.now()+timedelta(seconds=3)).isoformat()
        src=source_version(a,source,se,env=env);cfg=scopes.apply(a,src.pk,target.pk,te.pk,[]);transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
        time.sleep(max(0,(timezone.datetime.fromisoformat(env['effective_until'])-timezone.now()).total_seconds())+0.1)
        self.assertEqual(resolve(key,target).status,'EXPIRED');self.assertTrue(pin('EXPIRED'))
        Grant.objects.filter(case=source,user=a,action='policy.activate').update(active=False)
        self.assertEqual(resolve(key,target).status,'INVALID');self.assertFalse(pin('EXPIRED'))
        Grant.objects.filter(case=source,user=a,action='policy.activate').update(active=True)
        scopes.transition(a,src.pk,'revoked');self.assertEqual(resolve(key,target).status,'REVOKED');self.assertTrue(pin('REVOKED'))
        Grant.objects.filter(case=target,user=a,action='policy.configure').update(active=False)
        self.assertEqual(resolve(key,target).status,'INVALID');self.assertFalse(pin('REVOKED'))
        Grant.objects.filter(case=target,user=a,action='policy.configure').update(active=True)
        self.assertTrue(pin('REVOKED'))
    def test_bound_scope_value_and_synthetic_context_remain_exact(self):
        from tests.test_policy_scopes import fixture as scope_fixture,source_version
        from apps.policy import scopes
        from apps.policy.services import resolve
        a,source,target,se,te=scope_fixture();key='D04.iana_timezone'
        src=source_version(a,source,se,paths=['/0']);cfg=scopes.apply(a,src.pk,target.pk,te.pk,[{'path':'/0','value':'Africa/Lagos'}]);transition(a,cfg.pk,'validated');transition(a,cfg.pk,'active')
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_schedules_binding_current(%s),psl_schedules_policy_current(%s,%s)',[cfg.pk,str(target.pk),cfg.pk]);self.assertEqual(cursor.fetchone(),(True,True))
        target.synthetic=False;target.save(update_fields=['synthetic']);self.assertEqual(resolve(key,target).status,'INVALID')
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_schedules_policy_current(%s,%s)',[str(target.pk),cfg.pk]);self.assertFalse(cursor.fetchone()[0])
        target.synthetic=True;target.save(update_fields=['synthetic'])
        source.kind='support';source.save(update_fields=['kind']);self.assertEqual(resolve(key,target).status,'INVALID')
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_schedules_policy_current(%s,%s)',[str(target.pk),cfg.pk]);self.assertFalse(cursor.fetchone()[0])
        source.kind='project';source.save(update_fields=['kind'])
        newer=source_version(a,source,se);self.assertEqual(resolve(key,target).status,'INVALID')
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_schedules_policy_current(%s,%s)',[str(target.pk),cfg.pk]);self.assertFalse(cursor.fetchone()[0])
    def test_mapping_source_successor_holds_native_and_sql(self):
        f=self.f;self.start();self.advance();s=flow.schedule(self.work);review(f,s);self.advance();self.assertEqual(self.work.status,'verified',self.work.finding)
        old=f['source'];analysis.capture_source(f['actor'],f['case'].pk,old.batch_id,old.entity,old.accounting_basis,old.extracted_at,'complete',old.control_total,old.evidence_id,rev(f['case']))
        with self.assertRaises((ValidationError,PermissionDenied)):flow.verify(self.work,f['actor'])
        with self.assertRaises(DatabaseError),transaction.atomic():FactoryWork.objects.filter(pk=self.work.pk).update(status='verified')
