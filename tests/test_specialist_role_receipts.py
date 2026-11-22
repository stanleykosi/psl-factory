"""Three synthetic business approvals whose assigned teams cover all eight specialists."""

import hashlib
import json
import os
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TransactionTestCase

from adapters import case_uploads
from apps.agents.specialist_models import SpecialistReading
from apps.documents import controlled, delivery
from apps.documents.models import PublicationReceipt
from apps.finance import analysis, hrfinance
from apps.identity.models import Grant
from apps.policy.hrfinance_validators import AUTHORITY, DISCLOSURE
from apps.policy.services import register_reference
from apps.workflows.native_station_models import NativeStationUse
from tests import document_helpers, finance_analysis_helpers, hrfinance_helpers
from tests.helpers import activate, rev
from tests.native_station_helpers import assert_waiting, finish_station, start_station


# An explicit expected team makes a missing specialist an acceptance failure.
TEAMS = {"F02": {"A01", "A03", "A05"}, "P52": {"A02", "A06", "A08"}, "F35": {"A02", "A04", "A07"}}


def nominate(owner, case, proof, assignments):
    refs = [
        register_reference(owner, case.pk, f"fixture:receipt-review:{role}:{user.pk}",
                           "schema:psl/role-assignment/v1", {"role": role, "user_id": user.pk}, proof.pk).ref
        for role, user in assignments
    ]
    activate(owner, case, "D05.role_principal_assignments", refs, proof)


class ApprovalScenarios:
    def open_station(self, process, source):
        work = start_station(self, process, source)
        if self.live_provider:
            self.track_test_uploads(work)
        assert_waiting(self, work)
        return work

    def track_test_uploads(self, work):
        # The provider and private store are real. Track storage versions around
        # the native write so teardown can only remove files this run created.
        self.assertTrue(work.case.synthetic)
        client, bucket = case_uploads.bucket()
        self.addCleanup(client.close)
        uploaded = {}
        put = case_uploads.put

        def versions(key):
            pages = client.get_paginator("list_object_versions").paginate(Bucket=bucket, Prefix=key)
            return {entry["VersionId"] for page in pages
                    for entry in page.get("Versions", []) + page.get("DeleteMarkers", [])
                    if entry["Key"] == key}

        def track(key, data):
            expected = {row.key for row in SpecialistReading.objects.filter(work=work).exclude(sha256="")}
            self.assertIn(key, expected)
            prior = versions(key)
            self.assertFalse(prior - uploaded.get(key, set()), "An unrelated file already occupies this key.")
            try:
                put(key, data)
            finally:
                uploaded.setdefault(key, set()).update(versions(key) - prior)

        def cleanup():
            for key, owned in uploaded.items():
                for version_id in owned:
                    client.delete_object(Bucket=bucket, Key=key, VersionId=version_id)
                self.assertFalse(versions(key) & owned, "A synthetic specialist report version remains.")

        self.addCleanup(cleanup)
        self.enterContext(patch.object(case_uploads, "put", track))

    def record(self, work, decision, downstream, reviewer, user_of_advice):
        verified = finish_station(self, work, downstream)
        process = work.native_station.process
        packet = verified.handoff.packet
        self.assertNotEqual(work.actor_id, reviewer.pk)
        self.assertEqual(decision.actor_id, reviewer.pk)
        self.assertEqual(getattr(decision, "verdict", None) or decision.kind, "approve")
        use = NativeStationUse.objects.get(handoff=verified.handoff, actor=user_of_advice)
        self.assertLessEqual(verified.handoff.created_at, decision.created_at)
        self.assertLessEqual(decision.created_at, downstream.created_at)
        self.assertLessEqual(use.created_at, downstream.created_at)
        self.assertLessEqual(downstream.created_at, verified.created_at)
        members = list(packet.members.order_by("role"))
        self.assertCountEqual([row.role for row in members], TEAMS[process])
        for row in members:
            self.assertTrue(row.citation_lines)
            self.assertEqual(row.model, os.environ["OPENROUTER_MODEL"])
            self.assertEqual(hashlib.sha256(case_uploads.read(row)).hexdigest(), row.sha256)
            statement = {
                "mode": "openrouter" if self.live_provider else "simulated",
                "process": process, "role": row.role, "model": row.model, "private_report_sha256": row.sha256,
                "disposition": row.disposition, "cited_lines": row.citation_lines,
                "source_sha256": row.source_hash, "packet_sha256": verified.handoff.packet_sha256,
                "information_reviewer": packet.reviewer_id, "work": work.pk, "preparer": work.actor_id,
                "decision": [decision._meta.label_lower, decision.pk, decision.created_at.isoformat()],
                "reviewer": reviewer.pk, "receiving_actor": use.actor_id,
                "receipt": [verified.receiver_model, verified.receiver_pk, downstream.created_at.isoformat()],
                "verified_at": verified.created_at.isoformat(),
            }
            print("Specialist approval receipt " + json.dumps(statement, sort_keys=True), flush=True)

    def test_f02_trial_balance_review_and_mapping(self):
        owner, case, proof, config, rules, source, _, _ = finance_analysis_helpers.fixture(review=False)
        reviewer = get_user_model().objects.create_user("synthetic-finance-source-reviewer")
        Grant.objects.create(case=case, user=reviewer, action="finance.review")
        nominate(owner, case, proof["policy_decision"], [("Finance", reviewer)])
        evidence = proof["finance_review"]
        for component, purpose in analysis.PURPOSE.items():
            analysis.review(reviewer, case.pk, purpose, rules[component].pk, "Finance", "approve", evidence.pk,
                            "Verified the sample mapping, formula and calculation rules.", rev(case))
        work = self.open_station("F02", source)
        with self.assertRaises(PermissionDenied):
            analysis.review(owner, case.pk, "source", source.pk, "Finance", "approve", evidence.pk,
                            "A preparer without the independent nomination cannot approve.", rev(case))
        approval = analysis.review(reviewer, case.pk, "source", source.pk, "Finance", "approve", evidence.pk,
                                   "Verified the source inventory and declared total.", rev(case))
        mapping = analysis.map_source(owner, case.pk, source.pk, [], rev(case))
        self.assertEqual(mapping.result["status"], "complete")
        self.assertEqual(mapping.snapshot["source_review"]["id"], approval.pk)
        self.record(work, approval, mapping, reviewer, owner)

    def test_p52_approved_document_delivered_to_named_recipient(self):
        owner, case, proof, source, template, recipient, _, _ = document_helpers.publication_fixture()
        reviewer = get_user_model().objects.create_user("synthetic-pmo-document-reviewer")
        Grant.objects.create(case=case, user=reviewer, action="document.review_controlled")
        nominate(owner, case, proof, [("PM", owner), ("PMO Lead", reviewer)])
        version = document_helpers.drafted(owner, case, template, source)
        work = self.open_station("P52", version)
        controlled.request_review(owner, case.pk, version.pk, rev(case))
        with self.assertRaises(PermissionDenied):
            controlled.review_version(owner, case.pk, version.pk, "approve", "Not the appointed reviewer.", rev(case))
        approval = controlled.review_version(reviewer, case.pk, version.pk, "approve",
                                             "Verified the exact proposed audience copy.", rev(case))
        publication = controlled.reserve_publication(owner, case.pk, version.pk, rev(case))
        self.assertEqual(publication.review_id, approval.pk)
        self.assertTrue(delivery.run_publication_once(case_id=case.pk, job_id=publication.job.pk))
        received = PublicationReceipt.objects.get(publication=publication, recipient=recipient)
        self.record(work, approval, received, reviewer, owner)

    def test_f35_hr_approval_before_private_finance_receipt(self):
        f = hrfinance_helpers.fixture(configure=False)
        hr, finance, case, proofs = f["hr"], f["finance"], f["case"], f["e"]
        for component, key in ((AUTHORITY, "authority"), (DISCLOSURE, "disclosure")):
            hrfinance_helpers.policy(hr, case, component, f["config"][key], proofs["owner"])
        contract = hrfinance.contract(finance, case.pk, f["need"].pk, "private-reporting-period",
                                      proofs["hr_contract_source"].pk, rev(case))
        f["contract"] = contract
        work = self.open_station("F35", contract)
        with self.assertRaises(ValidationError):
            hrfinance_helpers.capture(f)
        approval = hrfinance.decide(hr, case.pk, contract.pk, "approve", "read-only",
                                    proofs["hr_disclosure_decision"].pk, rev(case))
        snapshot = hrfinance_helpers.capture(f)
        self.assertEqual(snapshot.manifest["authorization_id"], approval.pk)
        received = hrfinance_helpers.receive(f, snapshot)
        self.assertEqual(received.snapshot_id, snapshot.pk)
        self.record(work, approval, received, hr, finance)


class SimulatedRoleApprovalTests(ApprovalScenarios, TransactionTestCase):
    live_provider = False


@skipUnless(os.getenv("PSL_STATION_LIVE") == "1", "Explicit synthetic Railway checks service only.")
class LiveRoleApprovalTests(ApprovalScenarios, TransactionTestCase):
    live_provider = True
