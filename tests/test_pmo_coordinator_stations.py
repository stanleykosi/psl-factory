"""Synthetic PMO workflows through O01 and each named native receiver."""
import json
from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.utils import timezone

from apps.core.services import add_evidence
from apps.documents import controlled
from apps.documents.delivery import run_publication_once
from apps.documents.models import PublicationReceipt
from apps.finance.models import Handoff, SignedBaselineIntake
from apps.identity.models import Grant
from apps.pmo import approval_routing, commercial, delivery, planning, rfp
from apps.pmo.models import ApprovalRouteReceipt, CommercialDocumentBinding, DeliveryDocumentBinding, MeetingVersion
from tests.helpers import rev
from tests.native_station_helpers import assert_waiting, finish_station as verify_station, start_station


def finish_station(test, work, expected_receipt):
    from apps.workflows.native_station_models import NativeStationUse
    receipt = verify_station(test,work,expected_receipt)
    # P05 is a restricted recipient acknowledgement. P19 is an incoming
    # customer response; its use is checked when PMO adopts the signed baseline.
    if work.native_station.process not in {"P05", "P19"}:
        test.assertTrue(NativeStationUse.objects.filter(handoff=receipt.handoff).exists(), work.native_station.process)
    return receipt


class PMONativeStations(TransactionTestCase):
    def start(self, process, subject):
        work = start_station(self, process, subject)
        assert_waiting(self, work)
        return work

    def publish(self, actor, case, version):
        controlled.request_review(actor, case.pk, version.pk, rev(case))
        controlled.review_version(actor, case.pk, version.pk, "approve", "Reviewed this exact audience copy", rev(case))
        controlled.reserve_publication(actor, case.pk, version.pk, rev(case))
        self.assertTrue(run_publication_once(case_id=case.pk))
        return PublicationReceipt.objects.get(publication__version=version)

    def test_planning_source_team_alignment_and_scope_decisions(self):
        from tests import planning_helpers as h
        f = h.fixture()
        items = [self.start(process, f["packet"]) for process in ("P17","P18","P21","P25")]
        h.observe(f)
        ready = planning.prepare(f["a"], f["c"].pk, f["packet"].pk)
        for work in items:
            finish_station(self, work, ready)

    def test_department_receives_routed_request_separately_from_approval(self):
        from tests import approval_helpers as h
        f = h.fixture()
        work = self.start("P02", f["request"])
        job = approval_routing.reserve(f["actor"], f["case"].pk, f["request"].pk)
        self.assertTrue(approval_routing.run_once(case_id=f["case"].pk, job_id=job.pk))
        receipt = ApprovalRouteReceipt.objects.get(job=job)
        self.assertFalse(receipt.payload["approval_granted"])
        finish_station(self, work, receipt)

    def test_design_planning_kickoff_and_release_request(self):
        from tests.test_delivery import DeliveryFixture
        from apps.pmo.meetings import record_meeting
        f = DeliveryFixture()
        f.setup_delivery()
        sources = {kind: f.source(kind, {"requires_ui": False, "client_signoff_required": False}
                    if kind == "ui_applicability" else {}) for kind in delivery.PLANNING}
        works = [self.start(process, sources[kind]) for process, kind in (
            ("P22","ui_applicability"), ("P23","technical_design"), ("P24","test_strategy"))]
        a, c = f.actor, f.case
        plan = delivery.decide_planning(a, c.pk, f.d.pk, "approve", f.e["plan"].pk, "Reviewed all sources", rev(c))
        for work in works:
            finish_station(self, work, plan)
        phase = self.start("P63", plan)
        meeting = record_meeting(a, c.pk, "EXACT-KICKOFF", "kickoff", timezone.now(), "Delivery", "Agreed expectations",
                                 [a.pk], [], f.e["requirements"].pk, rev(c))
        kickoff = self.start("P27", meeting)
        record = delivery.record_progress(a, c.pk, f.d.pk, "kickoff", meeting.evidence_id,
                                          "Kickoff with reviewed plan", rev(c), meeting.pk)
        for work in (phase, kickoff):
            finish_station(self, work, record)
        f.gates(delivery.UPSTREAM_GATES)
        gates = [self.start(process, f.candidate.gates.get(kind=kind)) for process, kind in
                 (("P29","qa_exit"),("P30","uat_product_owner"),("P31","engineering_go"))]
        delivery.record_release_request(a, c.pk, f.d.pk, "SAMPLE-GLPI", f.e["requirements"].pk,
                                        "Actual synthetic deployment request", rev(c))
        f.gates(delivery.GLPI_GATES,"SAMPLE-GLPI")
        ready = delivery.prepare_readiness(a,c.pk,f.d.pk,rev(c))
        for work in gates:
            finish_station(self, work, ready)

    def test_retrospective_received_by_closure_document(self):
        from tests.test_delivery import DeliveryFixture
        from apps.pmo.delivery_documents import draft_delivery_document
        f = DeliveryFixture()
        f.setup_delivery()
        selection = f.closing()
        meeting = MeetingVersion.objects.get(pk=selection["retrospective_id"])
        work = self.start("P38", meeting)
        version = draft_delivery_document(f.actor, f.case.pk, f.d.pk, "closure", f.t.pk, selection, rev(f.case))
        finish_station(self, work, DeliveryDocumentBinding.objects.get(version=version))

    def test_sow_revision_approvals_templates_publication_and_signed_finance_receipt(self):
        from tests import test_commercial_changes as h, test_template_current as templates
        from tests.signature_helpers import packet_for
        a,c,e,t = h.fixture()
        proof = e["policy_decision"]
        scope = templates.scope(a,c,proof)
        templates.configure(a,c,proof,[t],[(scope,a)])
        template = self.start("P11",t)
        selection = self.start("P10",scope)
        claim = templates.claim(a,c,scope,t,proof)
        finish_station(self,template,claim)
        h.proposal(a,c,e)
        e["sow"] = add_evidence(a,c.pk,"sow","Revised services and planned milestone documentation","synthetic:project")
        e["costing"] = add_evidence(a,c.pk,"costing","Revised cost basis for approved scope change","synthetic:project")
        revised = h.proposal(a,c,e)
        approvals = [self.start(process,revised) for process in ("P08","P09")]
        h.approvals(a,c,revised)
        version = commercial.draft_submission(a,c.pk,revised.pk,t.pk,rev(c),template_scope_id=scope.pk)
        binding = CommercialDocumentBinding.objects.get(version=version)
        finish_station(self,selection,version)
        for work in approvals:
            finish_station(self,work,binding)
        publications = [self.start("P01",binding), self.start("P52",version), self.start("P53",version)]
        published = self.publish(a,c,version)
        for work in publications:
            finish_station(self,work,published)
        client = self.start("P19",published)
        response = commercial.capture_response(a,c.pk,revised.pk,published.pk,"signed",e["signature"].pk,
                                               "Customer supplied signed statement",rev(c))
        customer_receipt = finish_station(self,client,response)
        packet = packet_for(a,c,e,revised)
        signed = self.start("P20",packet)
        adoption = commercial.adopt_signed(a,c.pk,revised.pk,response.pk,rev(c))
        finish_station(self,signed,SignedBaselineIntake.objects.get(adoption=adoption))
        from apps.workflows.native_station_models import NativeStationUse
        self.assertTrue(NativeStationUse.objects.filter(handoff=customer_receipt.handoff,actor=a).exists())
        from apps.pmo.coordinator_commercial import client_response, commercial_packet, shared_submission
        self.assertEqual(commercial_packet(revised,a).receipt,binding)
        self.assertEqual(shared_submission(binding,a).receipt,published)
        self.assertEqual(client_response(published,a).receipt,response)

    def test_template_owner_resolves_competing_unconfirmed_claims_after_specialist_handoff(self):
        from django.core.exceptions import ValidationError
        from apps.documents import template_current
        from tests import test_commercial_changes as h, test_template_current as templates

        owner, case, evidence, original = h.fixture()
        proof = evidence["policy_decision"]
        competitor = controlled.register_template(owner,case.pk,original.name,h.DEFINITION,proof.pk,rev(case))
        scope = templates.scope(owner,case,proof)
        templates.configure(owner,case,proof,[original,competitor],[(scope,owner)])
        chosen = templates.claim(owner,case,scope,original,proof,False)
        competing = templates.claim(owner,case,scope,competitor,proof,False)
        claims = [chosen.pk,competing.pk]
        work = start_station(self,"P11",original)

        def resolve():
            return template_current.resolve_claims(owner,case.pk,scope.pk,chosen.pk,claims,proof.pk,
                                                   "Owner checked both sources and chose the original",rev(case))

        with self.assertRaises(ValidationError):
            resolve()
        self.assertFalse(scope.resolutions.exists())
        assert_waiting(self,work)
        resolution = resolve()
        finish_station(self,work,resolution)
        self.assertEqual(template_current.status(scope)["manifest"]["template_id"],original.pk)

    def test_milestone_received_by_finance(self):
        from tests.helpers import setup_case, signed
        from apps.pmo.services import complete_milestone
        from apps.workflows.services import run_once
        a,c = setup_case()
        e = signed(a,c)
        item = complete_milestone(a,c.pk,"Verified incremental milestone",e["completion"].pk,rev(c))
        work = self.start("P12",item)
        self.assertTrue(run_once())
        handoff = Handoff.objects.get(milestone=item)
        from apps.finance.services import begin_invoice_preparation
        begin_invoice_preparation(a,c.pk,handoff.pk,rev(c))
        finish_station(self,work,handoff)

    def test_bid_intake_assigned_to_project_manager(self):
        from tests.test_rfp import fixture
        a,c,e,_,_ = fixture(record_intake=False)
        intake = rfp.intake(a,c.pk,"BID-OWNED",e["rfp_intake"].pk,timezone.now(),"not_stated",None,None,
                            "Original request received",rev(c))
        work = self.start("P45",intake)
        manager = rfp.assign(a,c.pk,a,"CEO",e["policy_decision"].pk,"Project manager assigned",rev(c))
        finish_station(self,work,manager)

    def test_period_reporting_through_recipient_receipt(self):
        from tests.meeting_helpers import meetings_fixture
        from apps.pmo.reporting import draft_period_report
        a,c,_,_,_,template,_,_ = meetings_fixture()
        report = draft_period_report(a,c.pk,"weekly_client",timezone.now()-timedelta(days=7),
                                      timezone.now(),template.pk,"client",rev(c))
        work = self.start("P04",report)
        finish_station(self,work,self.publish(a,c,report.version))

    def test_sop_and_acceptance_by_independent_owners(self):
        from tests import validation_helpers as h
        from apps.documents import validation
        f = h.fixture()
        a,c = f["actor"],f["case"]
        selected = ["P13","P15"]
        clause = "Review the project plan before closing its Planning phase."
        source = h.evidence(a,c,"procedure_source",clause)
        metadata = dict(f["source"].metadata, document_kind="pmo_sop", process_ids=selected,
                       clauses=[dict(f["source"].metadata["clauses"][0], key="planning", quote=clause, process_ids=selected)])
        f["source"] = validation.capture_source(a,c.pk,"PMO procedure",source.pk,metadata,rev(c))
        f["examples"] = [validation.capture_example(a,c.pk,"PMO-"+example.scenario,selected,example.scenario,
                         example.expected,example.evidence_id,rev(c)) for example in f["examples"]]
        payload = dict(f["package"].payload, source_ids=[f["source"].pk], process_ids=selected,
                       example_ids=[ex.pk for ex in f["examples"]])
        f["package"] = validation.prepare_package(a,c.pk,"PMO owner review",payload,f["decision_evidence"].pk,rev(c))
        meaning = self.start("P13",f["source"])
        acceptance = self.start("P15",f["package"])
        finish_station(self,meaning,h.review(f,"meaning"))
        h.review(f,"expectations")
        h.replays(f)
        finish_station(self,acceptance,h.review(f,"acceptance"))

    def test_project_reader_acknowledges_only_its_current_projection(self):
        from apps.policy.operator_drafts import draft_operator_policy
        from apps.policy.project_view_validators import COMPONENT
        from apps.policy.services import transition
        from apps.pmo import project_view, coordinator_visibility
        from tests.test_delivery import DeliveryFixture
        f = DeliveryFixture()
        f.setup_delivery()
        f.plan()
        a,c = f.actor,f.case
        recipient = get_user_model().objects.create_user("station-view-recipient")
        Grant.objects.create(case=c,user=recipient,action="project.view")
        value = json.loads(Path("fixtures/project-view.json").read_text())["value"]
        value["discloser_id"] = a.pk
        profile = value["profiles"][0]
        profile["recipient_ids"] = [recipient.pk]
        policy = draft_operator_policy(a,c.pk,COMPONENT,value,f.e["policy_decision"].pk,timezone.now())
        transition(a,policy.pk,"validated")
        transition(a,policy.pk,"active")
        work = self.start("P05",policy.states.get(state="active"))
        view = project_view.projection(recipient,c.pk,profile["key"])
        receipt = coordinator_visibility.acknowledge(recipient,c.pk,profile["key"],coordinator_visibility.view_digest(recipient,view))
        finish_station(self,work,receipt)

    def test_external_issue_references_and_independent_closure_entries(self):
        from tests.test_issues import IssueTests
        from apps.pmo import issue_references as refs, issues
        f = IssueTests()
        f.setUp()
        a,c = f.a,f.c
        state = f.issue()
        evidence_by_kind = {"risk":"risk_reference", "incident":"incident"}
        references = []
        jobs = []
        for process,kind in (("P51","risk"),("P55","incident")):
            system = "Synthetic " + kind + " register"
            key = kind + "-17"
            original = add_evidence(a,c.pk,evidence_by_kind[kind],"Source-owned record reference","synthetic:source")
            contract = refs.configure(a,c.pk,kind,system,["status"],"supplied",f.fix.pk,rev(c))
            readback = {"protocol":"issue-reference-readback/v1","source_identity":system,"source_ref":key,
                        "observed_at":timezone.now().isoformat(),"availability":"available","fields":{"status":"Investigating"}}
            proof = add_evidence(a,c.pk,"agent_private_issue_readback",json.dumps(readback),"synthetic:"+kind)
            observed = refs.observe(a,c.pk,state.issue_id,state.pk,contract.pk,key,proof.pk,rev(c))
            jobs.append(self.start(process,observed))
            references.append({"kind":kind,"source_ref":key,"evidence_id":original.pk,"observation_id":observed.pk})
        change = add_evidence(a,c.pk,"change_request","Confirmed production change reference","synthetic:change")
        references.append({"kind":"change","source_ref":"change-17","evidence_id":change.pk})
        relation = {"incident_ref":"incident-17","change_ref":"change-17","evidence_id":f.fix.pk,"confirmed":True}
        revision = refs.correct(a,c.pk,state.issue_id,state.pk,None,references,[relation],f.fix.pk,
                                "Source owners confirmed the referenced issue and change",rev(c))
        for work in jobs:
            finish_station(self,work,revision)
        resolved = f.step(f.step(state,"acknowledge"),"resolve",fix_id=f.fix.pk,root_cause_id=f.rca.pk)
        closure = self.start("P54",resolved)
        for role in ("QA","PM"):
            issues.close_issue_log(a,c.pk,resolved.issue_id,resolved.pk,role,f.fix.pk,"Reviewed exact resolved issue",rev(c))
        resolved.issue.refresh_from_db()
        finish_station(self,closure,resolved.issue.current)

    def test_classification_and_approved_change_authorization(self):
        from tests.test_commercial_changes import ControlledChangeTests, impact_fixture
        from apps.pmo import changes
        f = ControlledChangeTests()
        f.setUp()
        a,c,v,proof = f.actor,f.case,f.cv,f.source
        classified = self.start("P56",v)
        approved = self.start("P58",v)
        assessments = [changes.assess_change(a,c.pk,v.pk,team,False,False,False,proof.pk,
                       "Confirmed ordinary change impact",rev(c),**impact_fixture(team)) for team in changes.CONTRIBUTORS]
        finish_station(self,classified,assessments[0])
        for role in ("Product","Engineering"):
            changes.decide_change(a,c.pk,v.pk,role,"approve",proof.pk,"Independent role decision",rev(c))
        authorization = changes.authorize_change(a,c.pk,v.pk,None,rev(c))
        finish_station(self,approved,authorization)
