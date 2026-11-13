"""Exact P54 external-source to P40/P42 boundary; synthetic supplied readback."""
import json
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.pmo import issue_references as refs
from apps.pmo.issues import log_issue
from apps.documents.controlled import current_version
from tests.test_leadership_reporting import LeadershipReportTests
from tests.helpers import rev


class IncidentReportBindingTests(LeadershipReportTests):
    def external_incident(self, source_ref='ENG-765'):
        self.incident_ref = source_ref
        for actor in [self.actor, self.recipient]:
            for action in ['case.read', 'issue.read', 'issue.reference.incident.read']:
                Grant.objects.get_or_create(case=self.case, user=actor, action=action)
        for action in ['issue.reference.configure', 'issue.reference.observe', 'issue.manage']:
            Grant.objects.get_or_create(case=self.case, user=self.actor, action=action)
        self.incident_evidence = add_evidence(self.actor, self.case.pk, 'incident',
            'Engineering incident reference, not a local severity decision', f'supplied:{source_ref}')
        self.issue_state = log_issue(self.actor, self.case.pk, source_ref, 'Production incident', 'Production',
            self.actor.pk, 'Read Engineering status', self.incident_evidence.pk,
            'Engineering retains incident ownership', rev(self.case))
        self.contract = refs.configure(self.actor, self.case.pk, 'incident', 'Engineering register',
            ['severity', 'opened_at', 'resolved_at', 'root_cause_ref'], 'supplied', self.notes.pk, rev(self.case))
        observation = self.observe_incident()
        self.reference_revision = refs.correct(self.actor, self.case.pk, self.issue_state.issue_id,
            self.issue_state.pk, None, [{'kind':'incident','source_ref':source_ref,
                'evidence_id':self.incident_evidence.pk,'observation_id':observation.pk}], [],
            self.notes.pk, 'Exact Engineering readback', rev(self.case))
        self.selections['issues'] = [self.issue_state.issue_id]
        self.payload['sections']['critical_incidents'] = {
            'text': 'Engineering reports P1 severity and a linked RCA as of the supplied observation; no PMO classification inferred.',
            'coverage': 'partial', 'evidence_ids': [self.incident_evidence.pk]}
        self.save_content()
        return observation

    def observe_incident(self, availability='available'):
        fields = {'severity':'P1','opened_at':'2026-10-01T10:00:00Z',
                  'resolved_at':None,'root_cause_ref':'ENG-RCA-765'} if availability=='available' else {}
        data = {'protocol':'issue-reference-readback/v1','source_identity':self.contract.source_identity,
            'source_ref':self.incident_ref,'observed_at':timezone.now().isoformat(),
            'availability':availability,'fields':fields}
        e = add_evidence(self.actor,self.case.pk,'agent_private_issue_readback',json.dumps(data),f'supplied:{self.incident_ref}-readback')
        return refs.observe(self.actor,self.case.pk,self.issue_state.issue_id,self.issue_state.pk,
            self.contract.pk,self.incident_ref,e.pk,rev(self.case))

    def test_incident_heavy_workbench_scale_and_revoked_provenance(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from django.urls import reverse
        from apps.documents import template_current
        from apps.documents.models import Version
        from apps.pmo.models import MinutesReportBinding
        from .test_template_current import claim, scope

        def prepare_incident(number):
            self.external_incident(f'INC-SCALE-{number}')
            return self.prepare()

        first = prepare_incident(0)
        source = template_current.capture_source(self.actor, self.case.pk, 'Synthetic incident scale source',
                                                 'synthetic:incident-scale', rev(self.case))
        applicability = scope(self.actor, self.case, source, document_type='status_report', audience='internal')
        claim(self.actor, self.case, applicability, self.template, source, False)
        Grant.objects.get_or_create(case=self.case, user=self.recipient, action='document.read')
        self.client.force_login(self.recipient)
        url = reverse('template_current', args=(self.case.pk,))

        def measured(label):
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(url)
            print(f'Incident workbench {label}: HTTP {response.status_code}, {len(queries)} SQL statements')
            return response, len(queries)

        # A retained pre-pin report version uses the same historical narrative
        # and the exact creation cutoff to reconstruct its incident citation.
        def retain_legacy(binding):
            version = binding.version
            copy = Version.objects.create(document=version.document, template=version.template,
                number=version.document.versions.count()+1, audience=version.audience,
                fields=version.fields, source_manifest=version.source_manifest, baseline_manifest=version.baseline_manifest,
                payload=version.payload, payload_sha256=version.payload_sha256, created_by=version.created_by)
            manifest = dict(binding.manifest)
            del manifest['incident_claims']
            MinutesReportBinding.objects.create(version=copy, report=binding.report, manifest=manifest)

        small, small_count = measured('one selected incident')
        bindings = [first] + [prepare_incident(number) for number in range(1, 12)]
        for binding in bindings[::2]:
            retain_legacy(binding)
        large, large_count = measured('12 distinct incidents and 6 legacy report versions')
        self.assertContains(small, self.template.name)
        self.assertContains(large, self.template.name)
        self.assertLessEqual(large_count, small_count + 25)
        Grant.objects.filter(case=self.case, user=self.recipient, action='issue.reference.incident.read').update(active=False)
        denied, _ = measured('observation scope withdrawn')
        self.assertNotContains(denied, self.template.name)
        self.assertNotContains(denied, f'sources/{source.pk}/')

    def test_batched_incidents_preserve_membership_observation_and_author_grants(self):
        from django.core.exceptions import PermissionDenied
        from apps.core.read_budget import ReadBudget
        from apps.pmo.incident_access_batch import IncidentAccess
        from apps.pmo.incident_reporting import selected_access

        observation = self.external_incident('PARITY-ONE')
        first = self.prepare().manifest['incident_claims'][0]
        foreign_observation = self.external_incident('PARITY-TWO')
        other = self.prepare().manifest['incident_claims'][0]
        invalid = [
            dict(first, revision_id=other['revision_id']),
            dict(first, observation_id=foreign_observation.pk),
            dict(first, reference=dict(first['reference'], source_ref='WRONG')),
            dict(first, reference=dict(first['reference'], evidence_id=observation.evidence_id)),
        ]

        def reader(pins):
            return IncidentAccess(self.recipient, [(self.case.pk, pin) for pin in pins], ReadBudget())

        batch = reader([first, *invalid])
        for path in (None, batch):
            selected_access(self.recipient, self.case, first, reader=path)
            for pin in invalid:
                with self.assertRaises(ValidationError):
                    selected_access(self.recipient, self.case, pin, reader=path)
        Grant.objects.filter(case=self.case, user=self.actor, action='issue.reference.observe').update(active=False)
        for path in (None, reader([first])):
            with self.assertRaises(PermissionDenied):
                selected_access(self.recipient, self.case, first, reader=path)

    def test_batched_legacy_history_keeps_distinct_cutoffs_and_fallback_state(self):
        from apps.core.read_budget import ReadBudget
        from apps.pmo.incident_access_batch import LegacyHistory
        from apps.pmo.incident_reporting import legacy_pins, narrative_citations

        self.external_incident()
        binding = self.prepare()
        legacy = dict(binding.manifest)
        del legacy['incident_claims']
        citations = narrative_citations(self.content.body)
        removed = refs.correct(self.actor, self.case.pk, self.issue_state.issue_id, self.issue_state.pk,
            self.reference_revision.pk, [], [], self.notes.pk, 'Later membership removal', rev(self.case))
        fallback = log_issue(self.actor, self.case.pk, 'RETAINED-STATE', 'Retained state source', 'Production',
            self.actor.pk, 'Read retained evidence', self.incident_evidence.pk, 'No revision history', rev(self.case),
            external_links=[{'kind': 'incident', 'source_ref': self.incident_ref, 'evidence_id': self.incident_evidence.pk}])
        fallback_manifest = dict(legacy, issues=[[fallback.issue_id, fallback.pk, self.incident_evidence.pk]])
        requests = [(legacy, binding.version.created_at), (legacy, removed.created_at),
                    (fallback_manifest, fallback.created_at)]
        budget = ReadBudget()
        history = LegacyHistory([(self.case.pk, manifest, at) for manifest, at in requests], budget)
        for (manifest, cutoff), count in zip(requests, (1, 0, 1)):
            expected = list(legacy_pins(self.case, manifest, cutoff, citations, budget=None))
            self.assertEqual(len(expected), count)
            self.assertEqual(list(legacy_pins(self.case, manifest, cutoff, citations, budget=budget, reader=history)), expected)

    def test_baseline_selected_source_unavailable_without_local_state_change(self):
        self.external_incident()
        binding = self.prepare()
        self.observe_incident('unavailable')
        self.issue_state.issue.refresh_from_db()
        self.assertEqual(self.issue_state.issue.current_id,self.issue_state.pk)
        self.assertEqual(refs.report(self.actor,self.issue_state.issue)['references'][0]['currentness'],'superseded')
        with self.assertRaises(ValidationError):
            current_version(self.case,binding.version_id)

    def sql_manifest(self):
        from django.db import connection
        inputs={'template_id':self.template.pk,'content_id':self.content.pk,
                'start_at':self.start.isoformat(),'end_at':self.end.isoformat(),
                'kind':self.kind,'audience':'internal','selections':self.selections}
        with connection.cursor() as cur:
            cur.execute('SELECT psl_leadership_manifest(%s,%s::jsonb)',[self.case.pk,json.dumps(inputs)])
            value=cur.fetchone()[0]
        return json.loads(value) if isinstance(value,str) else value

    def sql_access(self, actor, manifest):
        from django.db import connection
        with connection.cursor() as cur:
            cur.execute('SELECT psl_leadership_access(%s,%s,%s::jsonb)',[self.case.pk,actor.pk,json.dumps(manifest)])
            return cur.fetchone()[0]

    def test_exact_selected_provenance_and_sql_parity(self):
        from django.db import connection
        from apps.core.read_budget import ReadBudget
        from apps.documents import template_current, template_source_reader
        from apps.pmo import incident_reporting, leadership_reporting
        from .test_template_current import claim, scope

        observation=self.external_incident();binding=self.prepare()
        pin=binding.manifest['incident_claims'][0]
        self.assertEqual(pin['observation_id'],observation.pk)
        self.assertEqual(pin['revision_id'],self.reference_revision.pk)
        self.assertEqual(pin['fields']['severity'],'P1')
        self.assertIsNone(pin['fields']['resolved_at'])
        self.assertEqual(pin['freshness'],'unknown')
        self.assertEqual(self.sql_manifest(),binding.manifest)
        self.assertTrue(self.sql_access(self.actor,binding.manifest))
        self.assertIn(pin['observed_at'],binding.version.fields['executive_summary']['text'])
        self.assertNotIn('ENG-RCA-765',json.dumps(binding.version.payload))
        statements = []

        def trace(execute, sql, params, many, context):
            statements.append(sql)
            return execute(sql, params, many, context)

        with connection.execute_wrapper(trace):
            leadership_reporting.binding_access(self.actor, binding.version, budget=ReadBudget())
        for field in ('pmo_minutesreportbinding"."manifest', 'pmo_issuereferencerevision"."references'):
            self.assertTrue(any(field in sql and 'CASE WHEN' in sql for sql in statements))
        for field in ('core_evidence"."body', 'pmo_issuereferenceobservation"."fields', 'pmo_issuereferencecontract"."allowed_fields'):
            self.assertFalse(any(field in sql for sql in statements))

        legacy = dict(binding.manifest)
        del legacy['incident_claims']
        statements.clear()
        with connection.execute_wrapper(trace):
            incident_reporting.legacy_access(self.actor, self.case, legacy, binding.version.created_at, budget=ReadBudget())
        for field in ('core_evidence"."body', 'pmo_issuereferencerevision"."references'):
            queries = [sql for sql in statements if field in sql]
            self.assertTrue(queries)
            self.assertTrue(all('CASE WHEN' in sql for sql in queries), queries)

        source = template_current.capture_source(self.actor, self.case.pk, 'Private incident report template rationale',
                                                 'synthetic:incident-template', rev(self.case))
        applicability = scope(self.actor, self.case, source, document_type='status_report', audience='internal')
        claim(self.actor, self.case, applicability, self.template, source, False)
        statements.clear()
        with connection.execute_wrapper(trace):
            _, selected = template_source_reader._source(self.actor, self.case, ReadBudget(), source.pk)
        self.assertEqual(selected['body'], source.body)
        # Account, case and outer document-grant reads occur before _source.
        self.assertLessEqual(len(statements) + 3, template_source_reader.MAX_QUERIES)

    def test_revoked_selected_scope_blocks_current_and_historical_not_receipts(self):
        from apps.core.read_budget import ReadBudget
        from django.core.exceptions import PermissionDenied
        from apps.pmo import leadership_reporting as reports
        from apps.documents.controlled import reserve_publication
        from apps.documents.delivery import run_publication_once
        from apps.documents.models import PublicationReceipt
        self.external_incident();binding=self.prepare();self.approve(binding)
        publication=reserve_publication(self.actor,self.case.pk,binding.version_id,rev(self.case))
        run_publication_once(case_id=self.case.pk,job_id=publication.job.pk)
        original=list(PublicationReceipt.objects.filter(publication=publication).values())
        Grant.objects.filter(case=self.case,user=self.actor,action='issue.reference.incident.read').update(active=False)
        with self.assertRaises(PermissionDenied): reports.binding_access(self.actor,binding.version)
        with self.assertRaises(PermissionDenied): reports.binding_access(self.actor,binding.version,budget=ReadBudget())
        with self.assertRaises(ValidationError): current_version(self.case,binding.version_id)
        self.assertFalse(self.sql_access(self.actor,binding.manifest))
        self.assertEqual(original,list(PublicationReceipt.objects.filter(publication=publication).values()))

    def test_unavailable_requires_unknown_and_never_current_fields(self):
        self.external_incident();unavailable=self.observe_incident('unavailable')
        refs.correct(self.actor,self.case.pk,self.issue_state.issue_id,self.issue_state.pk,self.reference_revision.pk,
            [dict(self.reference_revision.references[0],observation_id=unavailable.pk)],[],self.notes.pk,'Source unavailable',rev(self.case))
        with self.assertRaises(ValidationError): self.prepare()
        self.assertIsNone(self.sql_manifest())
        self.payload['sections']['critical_incidents']={'text':'Engineering source unavailable; no current incident status is verified.',
            'coverage':'unknown','evidence_ids':[self.incident_evidence.pk]}
        self.save_content();binding=self.prepare()
        self.assertEqual(binding.manifest['incident_claims'][0]['fields'],{})
        self.assertEqual(binding.manifest['incident_claims'][0]['availability'],'unavailable')
        self.assertEqual(self.sql_manifest(),binding.manifest)

    def test_unrelated_membership_successor_does_not_invalidate_selected_claim(self):
        self.external_incident();binding=self.prepare()
        e=add_evidence(self.actor,self.case.pk,'incident','Unselected other incident','supplied:other-765')
        refs.correct(self.actor,self.case.pk,self.issue_state.issue_id,self.issue_state.pk,self.reference_revision.pk,
            self.reference_revision.references+[{'kind':'incident','source_ref':'OTHER-765','evidence_id':e.pk}],[],
            self.notes.pk,'Unrelated source membership',rev(self.case))
        current_version(self.case,binding.version_id)
        self.assertEqual(self.sql_manifest(),binding.manifest)
        self.assertEqual(self.prepare().pk,binding.pk)

    def test_removed_selected_membership_holds_new_claims(self):
        self.external_incident();binding=self.prepare()
        refs.correct(self.actor,self.case.pk,self.issue_state.issue_id,self.issue_state.pk,self.reference_revision.pk,
            [],[],self.notes.pk,'Remove erroneous link',rev(self.case))
        with self.assertRaises(ValidationError): current_version(self.case,binding.version_id)
        with self.assertRaises(ValidationError): self.prepare()
        self.assertIsNone(self.sql_manifest())

    def test_ambiguous_selected_citation_holds_without_guessing(self):
        self.external_incident()
        refs.correct(self.actor,self.case.pk,self.issue_state.issue_id,self.issue_state.pk,self.reference_revision.pk,
            self.reference_revision.references+[{'kind':'incident','source_ref':'OTHER-765','evidence_id':self.incident_evidence.pk}],[],
            self.notes.pk,'Ambiguous evidence association',rev(self.case))
        with self.assertRaises(ValidationError): self.prepare()
        self.assertIsNone(self.sql_manifest())

    def test_unselected_incident_and_client_inventory_unchanged(self):
        from adapters.pmo_reporting import LocalPMOReportingAdapter
        self.external_incident()
        snapshot=LocalPMOReportingAdapter().read_client_facts(self.case,self.start,self.end,timezone.now())['manifest']
        self.selections['issues']=[]
        self.payload['sections']['critical_incidents']['evidence_ids']=[self.notes.pk]
        self.save_content();binding=self.prepare()
        self.observe_incident('unavailable')
        Grant.objects.filter(case=self.case,user=self.actor,action='issue.reference.incident.read').update(active=False)
        current_version(self.case,binding.version_id)
        self.assertNotIn('incident_claims',binding.manifest)
        self.assertEqual(snapshot,LocalPMOReportingAdapter().read_client_facts(self.case,self.start,self.end,timezone.now())['manifest'])

    def test_original_uncertain_receipt_lookup_after_source_scope_loss(self):
        from apps.documents.controlled import reserve_publication
        from apps.documents.delivery import run_publication_once
        from apps.documents.models import PublicationReceipt
        from tests.test_leadership_reporting import LookupOnly
        from adapters.publications import PublicationTimeoutAfterAccept
        self.external_incident();binding=self.prepare();self.approve(binding)
        publication=reserve_publication(self.actor,self.case.pk,binding.version_id,rev(self.case))
        run_publication_once(PublicationTimeoutAfterAccept(),case_id=self.case.pk,job_id=publication.job.pk)
        publication.job.refresh_from_db();self.assertEqual(publication.job.status,'unknown')
        self.observe_incident('unavailable')
        Grant.objects.filter(case=self.case,user=self.actor,action='issue.reference.incident.read').update(active=False)
        run_publication_once(LookupOnly(),case_id=self.case.pk,job_id=publication.job.pk)
        publication.job.refresh_from_db();self.assertEqual(publication.job.status,'confirmed')
        self.assertEqual(PublicationReceipt.objects.filter(publication=publication).count(),1)

    def test_tuesday_explicit_source_claim_uses_same_binding(self):
        self.external_incident();self.kind='internal_tuesday';self.configure(self.kind)
        self.payload['sections']['risks']={'text':'Engineering source reports P1; PMO does not remap this severity.',
            'coverage':'partial','evidence_ids':[self.incident_evidence.pk]}
        self.save_content();binding=self.prepare()
        self.assertEqual(self.sql_manifest(),binding.manifest)
        self.observe_incident('unavailable')
        with self.assertRaises(ValidationError): current_version(self.case,binding.version_id)

    def test_source_export_supersession_and_config_authority_loss(self):
        from django.core.exceptions import PermissionDenied
        self.external_incident();binding=self.prepare()
        data={'protocol':'issue-reference-readback/v1','source_identity':self.contract.source_identity,
            'source_ref':'ENG-765','observed_at':timezone.now().isoformat(),'availability':'unavailable','fields':{}}
        add_evidence(self.actor,self.case.pk,'agent_private_issue_readback',json.dumps(data),'supplied:ENG-765-readback')
        with self.assertRaises(ValidationError): current_version(self.case,binding.version_id)
        self.assertIsNone(self.sql_manifest())
        Grant.objects.filter(case=self.case,user=self.actor,action='issue.reference.configure').update(active=False)
        self.assertFalse(self.sql_access(self.recipient,binding.manifest))
        from apps.pmo.leadership_reporting import binding_access
        with self.assertRaises(PermissionDenied): binding_access(self.recipient,binding.version)


from tests.test_factory_leadership import FactoryLeadershipTests


class FactoryIncidentReportTests(FactoryLeadershipTests):
    external_incident=IncidentReportBindingTests.external_incident
    observe_incident=IncidentReportBindingTests.observe_incident

    def test_factory_exact_incident_claim_approval_receipts_and_sql_rejection(self):
        from django.db import connection, transaction, DatabaseError
        from apps.workflows import factory_leadership as reporting
        from apps.workflows.models import FactoryWork
        from apps.documents.models import PublicationReceipt
        self.external_incident();self.inputs['content_id']=self.content.pk
        self.start_work();self.advance();version=self.review();self.advance()
        self.assertEqual(self.work.status,'verified',self.work.finding)
        receipts=list(PublicationReceipt.objects.values())
        with connection.cursor() as cur:
            cur.execute('SELECT psl_leadership_document(%s,%s,%s)',[self.work.pk,self.work.source_head_id,version.pk])
            self.assertTrue(cur.fetchone()[0])
        self.observe_incident('unavailable')
        with self.assertRaises(ValidationError): reporting.verify(self.work,self.actor)
        with self.assertRaises(DatabaseError),transaction.atomic():
            FactoryWork.objects.filter(pk=self.work.pk).update(finding='Stale incident claim is not current')
        self.assertEqual(receipts,list(PublicationReceipt.objects.values()))

    def test_factory_original_lookup_after_selected_scope_withdrawal(self):
        from apps.workflows import factory_leadership as reporting
        from tests.test_leadership_reporting import LookupOnly
        from apps.documents.models import PublicationReceipt
        self.external_incident();self.inputs['content_id']=self.content.pk
        job=self.uncertain();receipt=PublicationReceipt.objects.get(publication=job.publication)
        self.observe_incident('unavailable')
        Grant.objects.filter(case=self.case,user=self.actor,action='issue.reference.incident.read').update(active=False)
        reporting.reconcile(self.actor,self.work.pk,self.work.revision,adapter=LookupOnly())
        job.refresh_from_db();self.assertEqual(job.status,'confirmed')
        self.assertEqual(PublicationReceipt.objects.get(publication=job.publication).pk,receipt.pk)
