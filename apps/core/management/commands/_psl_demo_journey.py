"""The real PSL journey for the demo projects: bid, engagement, planning, costing and signed SOW.

Each step runs through the same line or service the application uses, so the project Journey lists real work
items. Until go-live the costing rule is a TEMPLATE rule and the engineering lead is a PLACEHOLDER (D-214);
the PM or PMO Lead logs the engineering decisions. Both are labelled as placeholders in the records.
"""
import json
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.services import add_evidence
from apps.documents.controlled import register_template, review_version
from apps.documents.models import PublicationReceipt
from adapters.commercial_intake import FIELDS
from apps.pmo import approvals, commercial, commercial_intake, costing, engagement, planning, rfp
from apps.pmo.models import ApprovalRequest, CommercialCase, RFPDisposition, RFPSubmission
from apps.policy.approval_drafts import draft_approval_policy
from apps.policy.approval_validators import CONTRACTS, ROUTES
from apps.policy.costing_drafts import draft_costing_policy
from apps.policy.engagement_validators import ASSIGN, REGISTER
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.planning_validators import COMPONENT as PLANNING_CRITERIA
from apps.policy.services import register_reference, transition
from apps.pmo.meetings import record_meeting
from apps.workflows import factory, factory_commercial, factory_engagement, factory_rfp
from apps.workflows.models import FactoryWork

PLACEHOLDER_ENGINEERING_LEAD = 'Placeholder engineering lead (D-214)'
PLACEHOLDER_PRODUCT_OWNER = 'Placeholder product owner (D-214, extended)'
TEMPLATE_RULE = 'Template costing rule (D-214)'
RFP_DEFINITION = {
    'document_type': 'rfp_response',
    'required_fields': ['executive_summary', 'scope', 'requirements_mapping', 'commercial_terms'],
    'audience_fields': {'client': ['executive_summary', 'scope', 'requirements_mapping', 'commercial_terms',
                                   'timeline', 'risks', 'dependencies', 'status']}}
SOW_DEFINITION = {
    'document_type': 'sow', 'required_fields': ['executive_summary', 'scope', 'timeline'],
    'audience_fields': {'client': ['executive_summary', 'scope', 'timeline', 'risks', 'dependencies', 'status']}}
PLANNING_SYSTEMS = {'scope': 'synthetic-planning-scope', 'estimates': 'synthetic-planning-estimates'}
RFP_KINDS = ['rfp_intake', 'rfp_commercial_terms', 'rfp_response', 'rfp_outcome', 'rfp_lessons', 'qa_estimate',
             'product_input']
# What the PMs and the PMO Lead need on a project to run its history; staff scopes still apply on top.
JOURNEY_PM = [
    'rfp.prepare', 'rfp.review', 'rfp.outcome', 'rfp.submit', 'rfp.dispose', 'rfp.contribute:Engineering',
    'rfp.contribute:QA', 'rfp.contribute:Security', 'rfp.contribute:Product', 'commercial.prepare',
    'commercial.decide', 'commercial.submit', 'commercial.read', 'commercial.proof.read', 'costing.read',
    'costing.source.read', 'costing.calculate', 'costing.bind', 'engagement.assign', 'engagement.register',
    'planning.read', 'planning.prepare', 'planning.coordinate', 'planning.route', 'planning.participate',
    'approval.read', 'approval.request', 'approval.route', 'policy.read', 'agent.rfp', 'agent.commercial',
    'agent.engagement', 'agent.planning', 'agent.costing', 'agent.extract', 'delivery.source', 'delivery.verify',
]
JOURNEY_PMO_LEAD = [
    'rfp.assign', 'rfp.read', 'rfp.review', 'commercial.decide', 'commercial.read', 'engagement.register',
    'engagement.capture', 'costing.read', 'costing.source.read', 'costing.rule.review', 'document.review_controlled',
    'document.read', 'planning.read', 'planning.compare', 'meeting.read', 'factory.read',
]
JOURNEY_FOLAKE = ['commercial.decide', 'commercial.read', 'factory.read']
JOURNEY_ADA = ['costing.read', 'costing.source.read', 'costing.oracle.review']


class JourneyMixin:
    def rev(self, case):
        case.refresh_from_db()
        return case.revision

    def profile(self, case, component, fixture, owner, **values):
        value = json.loads(Path(settings.BASE_DIR, 'fixtures', fixture).read_text())
        value.pop('classification')
        value.update(values)
        config = draft_operator_policy(self.admin, case.pk, component, value, owner.pk,
                                       timezone.now() - timedelta(minutes=1))
        transition(self.admin, config.pk, 'validated')
        transition(self.admin, config.pk, 'active')
        return value

    def technical_person(self, username, full_name):
        user = get_user_model().objects.filter(username=username).first()
        if user is None:
            user = get_user_model().objects.create_user(username, first_name=full_name)
            user.set_unusable_password()
            user.save()
        return user

    def run(self, work):
        factory.run_until_wait(work.pk)
        work.refresh_from_db()
        return work

    # -- documents ------------------------------------------------------------------------------------

    def documents_setup(self, key):
        """Templates, the client recipient and the bid route, activated once for the project."""
        case, owner = self.cases[key], self.e[key]['policy_decision']
        recipient = self.technical_person(
            'psl-demo-client-recipient' if key == 'lagoon' else f'psl-demo-client-recipient-{key}',
            self.projects[key]['client'] + ' project contact')
        self.grant_user(case, recipient, ['document.receive:client'])
        templates = {'rfp': register_template(self.admin, case.pk, 'RFP response', RFP_DEFINITION, owner.pk,
                                              self.rev(case)),
                     'sow': register_template(self.admin, case.pk, 'Project SOW', SOW_DEFINITION, owner.pk,
                                              self.rev(case))}
        if key == 'lagoon':
            templates['report'] = register_template(self.admin, case.pk, 'Weekly client report', self.report_definition,
                                                    owner.pk, self.rev(case))
        self.templates[key] = templates
        self.recipients[key] = recipient
        ref = register_reference(self.admin, case.pk, f'psl-demo:recipient:{key}', 'schema:psl/document-recipient/v1',
                                 {'audience': 'client', 'user_id': recipient.pk}, owner.pk)
        self.activate(case, owner, 'D11.recipient_grant_refs', [ref.ref])
        self.artifact(case, owner, 'D11.template_storage_retention_rules', 'schema:psl/document-storage/v1', {
            'template_ids': [template.pk for template in templates.values()],
            'repository': 'internal-versioned', 'retention_days': 30})
        route = {'kind': 'rfp_submission', 'key': 'client_bid', 'method': 'internal_recipient_inbox',
                 'destination_ref': 'synthetic:rfp-inbox', 'recipient_ids': [recipient.pk], 'sender_roles': ['PM']}
        route_ref = register_reference(self.admin, case.pk, f'psl-demo:rfp-route:{key}',
                                       'schema:psl/rfp-submission-route/v1', route, owner.pk)
        self.activate(case, owner, 'D11.adapter_configuration_refs', [route_ref.ref])

    # -- the bid --------------------------------------------------------------------------------------

    def rfp_history(self, key):
        """RFP received, the PMO Lead assigns the PM, the response is reviewed, sent and won."""
        case, project, e = self.cases[key], self.projects[key], self.e[key]
        pm, kemi, folake = self.users[project['pm']], self.users['kemi'], self.users['folake']
        evidence = {kind: self.evidence(case, kind, f'{project["title"]}: {kind.replace("_", " ")} (demo record).')
                    for kind in RFP_KINDS}
        rfp.intake(self.admin, case.pk, f'PSL-DEMO-RFP-{key.upper()}', evidence['rfp_intake'].pk,
                   timezone.now() - timedelta(hours=2), 'not_stated', None, None,
                   'The received document states no deadline', self.rev(case))
        rfp.assign(kemi, case.pk, pm, 'PMO Lead', e['policy_decision'].pk, 'The PMO Lead assigns the accountable PM',
                   self.rev(case))
        # The PM logs the engineering input; it is recorded for the placeholder engineering lead (D-214).
        for team, kind in rfp.TEAMS.items():
            rfp.contribute(pm, case.pk, team, evidence[kind].pk if kind in evidence else e[kind].pk, self.rev(case))
        value = self.profile(case, 'OPS.factory_rfp_execution', 'factory-rfp.json', e['policy_decision'],
                             executor_id=pm.pk, template_id=self.templates[key]['rfp'].pk, route_key='client_bid')
        payload = {'response_evidence': evidence['rfp_response'].pk,
                   'public_terms': evidence['rfp_commercial_terms'].pk,
                   'sources': {kind: e[kind].pk for kind in ['requirements', 'plan', 'costing']},
                   'matrix': [{'key': 'R1', 'evidence_id': e['requirements'].pk, 'response': 'Cited coverage',
                               'disposition': 'addressed'}],
                   'lessons': evidence['rfp_lessons'].pk}
        work = factory_rfp.start(pm, case.pk, f'PSL-DEMO-RFP-{key.upper()}', payload,
                                 f'Bid response: {project["title"]}', self.rev(case))
        self.run(work)
        response = factory_rfp.response_for(work)
        assert response is not None, work.finding
        rfp.review(kemi, case.pk, response.pk, 'PMO Lead', 'approve', e['policy_decision'].pk,
                   'The PMO Lead reviewed the exact response', self.rev(case))
        rfp.review(pm, case.pk, response.pk, 'Engineering Lead', 'approve', e['policy_decision'].pk,
                   f'Engineering decision logged by the PM for the {PLACEHOLDER_ENGINEERING_LEAD}', self.rev(case))
        for role, person in [('PM', pm), ('Head of PMO', kemi), ('CEO', folake)]:
            commercial.decide_proposal(person, case.pk, response.commercial_id, role, 'approve',
                                       'Reviewed the exact costing and proposal for the bid', self.rev(case))
        self.run(work)
        document = factory_rfp.document_for(work, value)
        assert document is not None, work.finding
        review_version(kemi, case.pk, document.pk, 'approve', 'The PMO Lead reviewed the exact client response',
                       self.rev(case))
        self.run(work)
        submission = RFPSubmission.objects.get(response=response)
        rfp.outcome(pm, case.pk, submission.pk, 'won', timezone.now(), 'Client', evidence['rfp_outcome'].pk,
                    'The client confirmed the award; recorded by the PM', self.rev(case))
        self.run(work)
        assert work.status == 'verified', work.finding

    # -- the engagement -------------------------------------------------------------------------------

    def engagement_history(self, key):
        """Register the engagement from the won bid: the PMO Lead assigns and registers it."""
        case, project, e = self.cases[key], self.projects[key], self.e[key]
        pm, kemi = self.users[project['pm']], self.users['kemi']
        values = json.loads(Path(settings.BASE_DIR, 'fixtures/engagement-intake.json').read_text())
        for component, rules in ((ASSIGN, values['assignment']), (REGISTER, values['registration'])):
            config = draft_operator_policy(self.admin, case.pk, component, rules, e['policy_decision'].pk,
                                           timezone.now() - timedelta(minutes=1))
            transition(self.admin, config.pk, 'validated')
            transition(self.admin, config.pk, 'active')
        self.profile(case, 'OPS.factory_engagement_execution', 'factory-engagement.json', e['policy_decision'])
        source = self.evidence(case, 'engagement_source', f'{project["client"]} ownership and scope (demo record).')
        disposition = RFPDisposition.objects.get(rfp__case=case, kind='route_a')
        work = factory_engagement.receive(pm, case.pk, f'PSL-DEMO-ENGAGEMENT-{key.upper()}', 'A', source.pk,
                                          f'PSL-DEMO-{key.upper()}', self.rev(case), disposition.pk)
        self.engagement_work[key] = work
        self.run(work)
        engagement.assign(kemi, case.pk, pm.pk, 'PMO Lead', source.pk, f'psl-demo-assignment-{key}')
        self.run(work)
        engagement.register(kemi, case.pk, f'PSL-{key.upper()}-001', 'PMO Lead', source.pk, e['plan'].pk,
                            f'psl-demo-registration-{key}')
        self.run(work)

    # -- costing and the signed SOW -------------------------------------------------------------------

    def template_costing(self, key):
        """The template costing rule (D-214): owner and independent tester are named; PSL replaces it at go-live."""
        case, e = self.cases[key], self.e[key]
        kemi, ada = self.users['kemi'], self.users['ada']
        values = json.loads(Path(settings.BASE_DIR, 'fixtures/commercial-costing.json').read_text())

        def record(kind, body):
            text = json.dumps(body) if isinstance(body, (dict, list)) else body
            return add_evidence(self.admin, case.pk, kind, text, 'synthetic:psl-demo-template-costing')

        rule = values['rule']
        rule.update(owner_id=kemi.pk, oracle_owner_id=ada.pk)
        rule['parameters'][0]['evidence_id'] = record('p14_parameter', f'{TEMPLATE_RULE}: hourly rate').pk
        rule_row = costing.capture_rule(self.admin, case.pk, 'calculator', record('p14_rule', rule).pk)
        note = record('p14_review', f'{TEMPLATE_RULE}: reviewed by its named owners')
        rule_review = costing.review(kemi, case.pk, rule_row.pk, None, 'confirm', f'rule-{key}', note.pk)
        oracle = {'rule_sha256': rule_row.sha256, 'calculator_ref': rule['calculator_ref'],
                  'calculator_version': rule['calculator_version'], 'source_class': 'synthetic_fixture',
                  'source_locator': 'independently-entered-example-fixture', 'scenarios': values['scenarios']}
        oracle_row = costing.capture_oracle(self.admin, case.pk, rule_row.pk, 'independent',
                                            record('p14_oracle', oracle).pk)
        oracle_review = costing.review(ada, case.pk, rule_row.pk, oracle_row.pk, 'confirm', f'oracle-{key}', note.pk)
        config = draft_costing_policy(self.admin, case.pk, {
            'rule_id': rule_row.pk, 'rule_sha256': rule_row.sha256, 'rule_review_id': rule_review.pk,
            'oracle_id': oracle_row.pk, 'oracle_sha256': oracle_row.sha256, 'oracle_review_id': oracle_review.pk},
            e['policy_decision'].pk, timezone.now() - timedelta(seconds=1))
        transition(self.admin, config.pk, 'validated')
        transition(self.admin, config.pk, 'active')
        return rule_row, oracle_row, record('p14_inputs', values['scenarios'][0]['inputs'])

    def costing_history(self, key, approvals):
        """Costing on the template rule through the commercial line, then the roles named in `approvals` decide."""
        case, project, e = self.cases[key], self.projects[key], self.e[key]
        pm = self.users[project['pm']]
        rule, oracle, inputs = self.template_costing(key)
        sources = {name: None for name in FIELDS}
        sources.update({name: e[name].pk for name in commercial_intake.PUBLIC})
        # The project contract follows the won bid's proposal, which is the case's current commercial record.
        bid = CommercialCase.objects.filter(case=case).values_list('current_id', flat=True).first()
        sources.update(predecessor_id=bid, inputs=inputs.pk, rule_id=rule.pk, oracle_id=oracle.pk,
                       template_id=self.templates[key]['sow'].pk,
                       context_id=e['requirements'].pk)
        head = commercial_intake.capture(pm, case.pk, sources, None, self.rev(case))
        self.profile(case, 'OPS.factory_commercial_execution', 'factory-commercial.json', e['policy_decision'],
                     executor_id=pm.pk)
        work = factory_commercial.start(pm, case.pk, f'PSL-DEMO-COMMERCIAL-{key.upper()}', head.pk,
                                        f'Costing: {project["title"]}', self.rev(case))
        self.commercial_work[key] = work
        self.run(work)
        revision = factory_commercial.proposal(work)
        assert revision is not None, work.finding
        who = {'PM': pm, 'Head of PMO': self.users['kemi'], 'CEO': self.users['folake'], 'PMO Lead': self.users['kemi']}
        for role in approvals:
            commercial.decide_proposal(who[role], case.pk, revision.pk, role, 'approve',
                                       f'{role} reviewed the exact costing on the {TEMPLATE_RULE}', self.rev(case))
        if len(approvals) < 4:
            return self.run(work), revision
        self.run(work)
        version = factory_commercial.document(work)
        review_version(self.users['kemi'], case.pk, version.pk, 'approve', 'The PMO Lead reviewed the exact SOW',
                       self.rev(case))
        self.run(work)
        assert work.status == 'verified', work.finding
        return work, revision

    def sign_sow(self, key, revision):
        """The client signs the delivered SOW; the PM records the response and the baseline is adopted."""
        case, e, pm = self.cases[key], self.e[key], self.users[self.projects[key]['pm']]
        receipt = PublicationReceipt.objects.get(publication__version__commercialdocumentbinding__revision=revision)
        response = commercial.capture_response(pm, case.pk, revision.pk, receipt.pk, 'signed', e['signature'].pk,
                                               'The PM recorded the client signature on the delivered SOW',
                                               self.rev(case))
        self.signature_packet(case, e, pm, revision)
        commercial.adopt_signed(pm, case.pk, revision.pk, response.pk, self.rev(case))


    # -- planning -------------------------------------------------------------------------------------

    def planning_history(self, key, handoff=False):
        """Planning hands the engagement to delivery: two alignment meetings and two department observations."""
        case, e = self.cases[key], self.e[key]
        pm, owner = self.users[self.projects[key]['pm']], e['policy_decision']
        work = FactoryWork.objects.get(case=case, definition='planning/v1')
        examples = json.loads(Path(settings.BASE_DIR, 'fixtures/planning-packet.json').read_text())
        approval = json.loads(Path(settings.BASE_DIR, 'fixtures/approval-routing.json').read_text())
        self.profile(case, 'OPS.factory_planning_execution', 'factory-planning.json', owner)
        # Once the SOW is signed the plan is compared with it; the PMO Lead is the independent reviewer.
        criteria = dict(examples['criteria'], comparison_reviewer_id=self.users['kemi'].pk,
                        comparison_reviewer_role='PMO Lead')
        config = draft_operator_policy(self.admin, case.pk, PLANNING_CRITERIA, criteria, owner.pk,
                                       timezone.now() - timedelta(minutes=1))
        transition(self.admin, config.pk, 'validated')
        transition(self.admin, config.pk, 'active')
        owners = {'scope': self.users['placeholder_po'], 'estimates': self.users['placeholder_eng']}
        for person in owners.values():
            self.grant_user(case, person, ['case.read', 'approval.read', 'approval.contract', 'approval.verify',
                                           'approval.receive'])
        routes, contracts = approval['routes'], approval['contracts']
        route, contract = routes['routes'][0], contracts['contracts'][0]
        routes['routes'], contracts['contracts'] = [], []
        for name, kind in planning.SUBJECTS.items():
            routes['routes'].append(dict(
                route, kind=kind, gate_kind=None, source_owner=planning.OWNER_ROLES[name], owner_id=owners[name].pk,
                owner_role=planning.OWNER_ROLES[name], source_actor_ref=f'synthetic-{name}',
                system=PLANNING_SYSTEMS[name]))
            contracts['contracts'].append(dict(contract, kind=kind, contract_evidence_id=owner.pk,
                                               required_subject_fields=[]))
        for component, value in ((ROUTES, routes), (CONTRACTS, contracts)):
            config = draft_approval_policy(self.admin, case.pk, component, value, owner.pk,
                                           timezone.now() - timedelta(minutes=1))
            transition(self.admin, config.pk, 'validated')
            transition(self.admin, config.pk, 'active')
        for name, person in owners.items():
            self.grant_user(case, person, ['approval.source.read:' + PLANNING_SYSTEMS[name]])
            self.grant_user(case, self.admin, ['approval.source.read:' + PLANNING_SYSTEMS[name]])
            self.grant_user(case, pm, ['approval.source.read:' + PLANNING_SYSTEMS[name]])
            proof = self.evidence(case, 'approval_contract_review',
                                  f'{planning.OWNER_ROLES[name]} accepts the evidence contract (placeholder owner)')
            approvals.review_contract(person, case.pk, planning.SUBJECTS[name], proof.pk)
        packet = planning.latest(case, 'packet')
        # The packet taken from the won bid declares where each source stands against the PRD and scope.
        payload = planning.packet(case, packet.pk)[1]['payload']
        payload['source_correlations'] = [
            {'key': field, 'source_field': field, 'source_id': payload[field], 'document_version': 'psl-demo-v1',
             'target_prd_id': payload['prd_id'], 'target_scope_id': payload['scope_id'], 'evidence_id': payload[field],
             'state': 'current', 'detail': 'Declared in the won bid and checked by the PM (demo record).',
             'resolution_id': None} for field in ('scope_id', 'engineering_estimate_id', 'security_estimate_id')]
        packet = planning.capture(pm, case.pk, payload, packet.pk)
        now = timezone.now()
        for offset, purpose in enumerate(planning.PURPOSES):
            meeting = record_meeting(pm, case.pk, f'PSL-DEMO-ALIGN-{key.upper()}-{offset}', 'alignment',
                                     now - timedelta(minutes=10 - offset), purpose,
                                     'Planning alignment held with the team (demo record)', [pm.pk], [],
                                     e['requirements'].pk, self.rev(case))
            planning.align(pm, case.pk, packet.pk, purpose, meeting.pk)
        self.run(work)
        requests = planning.open_requests(pm, case.pk, packet.pk)['requests']
        for name, request_id in requests.items():
            source = self.evidence(case, 'approval_source', json.dumps({
                'request_id': request_id, 'kind': planning.SUBJECTS[name],
                'subject': ApprovalRequest.objects.get(pk=request_id).subject,
                'system': PLANNING_SYSTEMS[name], 'source_owner': planning.OWNER_ROLES[name],
                'source_actor_ref': f'synthetic-{name}', 'external_ref': f'PSL-DEMO-{key.upper()}-{name.upper()}',
                'source_version': 'v1', 'decision': 'accepted', 'decided_at': timezone.now().isoformat(),
                'signature_ref': 'synthetic-owner-signature-reference', 'critical_defects': None}))
            receipt = approvals.capture(self.admin, case.pk, request_id, source.pk)
            observation = self.evidence(case, 'approval_observation', json.dumps({
                'receipt_id': receipt.pk, 'system': receipt.system, 'external_ref': receipt.external_ref,
                'source_version': receipt.source_version, 'observed_at': timezone.now().isoformat(),
                'outcome': 'available', 'payload_sha256': receipt.sha256, 'decision': 'accepted'}))
            approvals.observe(owners[name], case.pk, receipt.pk, observation.pk)
        if handoff:
            self.run(work)

    def planning_handoff(self, key):
        """The backend creates the plan, costing and SOW baseline only when the SOW is signed.

        For a project that is not signed (Kora) the handoff stops with that finding.
        """
        case, e = self.cases[key], self.e[key]
        work = FactoryWork.objects.get(case=case, definition='planning/v1')
        packet = planning.latest(case, 'packet')
        comparison = self.evidence(case, 'sow', 'The signed SOW matches the planning packet, as compared by the PMO '
                                                'Lead (demo record).')
        planning.compare(self.users['kemi'], case.pk, packet.pk, 'no_difference', comparison.pk)
        self.run(work)
