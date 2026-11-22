"""Authenticated department read, decision and private receipt boundaries."""
from unittest.mock import patch

from django.test import Client, TransactionTestCase
from django.urls import reverse

from apps.finance import hrfinance
from apps.identity.team_models import StaffMembership
from apps.policy.hrfinance_validators import AUTHORITY, DISCLOSURE
from apps.policy.services import register_reference
from tests import hrfinance_helpers as hr, planning_helpers
from tests.helpers import activate, rev
from tests.native_station_helpers import assert_waiting, finish_station, start_station
from tests.process_role_helpers import role_accounts


class NativeRoleAccess(TransactionTestCase):
    @staticmethod
    def client_for(actor):
        client = Client()
        client.force_login(actor)
        return client

    def test_department_members_read_current_work_without_model_or_decision_grants(self):
        from apps.pmo import planning
        from apps.workflows.native_station_access import read_work
        from django.http import Http404

        f = planning_helpers.fixture()
        actor, case = f["a"], f["c"]
        work = start_station(self, "P17", f["packet"])
        users = role_accounts(case)
        project = f"/api/v1/projects/{case.pk}/department-handoffs"
        page = reverse("factory_detail", args=[work.pk])
        api = f"/api/v1/work/{work.pk}/department-handoff"
        for key, user in users.items():
            with self.subTest(staff=key):
                client = self.client_for(user)
                expected = key in ("pmo_head", "pmo_member")
                listing = client.get(project)
                self.assertEqual(any(row["work_id"] == work.pk for row in listing.json().get("items", [])), expected)
                details = client.get(api)
                self.assertEqual(details.status_code, 200 if expected else 404)
                self.assertEqual(client.get(page).status_code, 200 if expected else 404)
                self.assertEqual(client.post(api + "/source-review", {"packet_id": 1, "digest": "f"*64,
                                "reason":"Reviewed this source"}, content_type="application/json").status_code, 404)
                if expected:
                    self.assertIsNone(details.json()["source_review"])
                    self.assertIsNone(details.json()["receipt"])
                    self.assertIsNone(details.json()["finance_acknowledgement"])
        member = users["pmo_member"]
        from apps.identity import teams
        membership = StaffMembership.objects.get(case=case, user=member, active=True)
        teams.revoke(membership.invitation.authority.user, case.pk, membership.pk,
                     "The synthetic member has left this project.")
        with self.assertRaises(Http404):
            read_work(member,work.pk)
        self.assertIn(self.client_for(member).get(api).status_code, (401,404))
        assert_waiting(self,work)
        planning_helpers.observe(f)
        ready = planning.prepare(actor,case.pk,f["packet"].pk)
        with patch.dict("os.environ", PSL_VERIFY_NATIVE_ROLES="0"):
            finish_station(self,work,ready)
        self.assertIsNotNone(self.client_for(actor).get(api).json()["receipt"])
        # The verified packet now cites two different departments' private approval sources.
        self.assertEqual(self.client_for(users["pmo_head"]).get(api).status_code, 404)

    def test_only_the_appointed_finance_member_can_acknowledge_hr_metadata(self):
        f = hr.fixture(configure=False)
        case, owner, first, proof = f["case"], f["hr"], f["finance"], f["e"]
        users = role_accounts(case)
        named = users["finance_member"]
        principals = []
        for user, role in [(owner, "HR"), (first, "Finance"), (named, "Finance")]:
            principals.append(register_reference(owner, case.pk, f"role-check-{user.pk}", "schema:psl/role-assignment/v1",
                              {"role":role, "user_id":user.pk}, proof["owner"].pk).ref)
        activate(owner,case,"D05.role_principal_assignments",principals,proof["owner"])
        cfg = f["config"]
        cfg["authority"]["assignments"].append({"user_id":named.pk,"role":"Finance","purpose":"receive"})
        cfg["disclosure"]["recipient_ids"] = [first.pk,named.pk]
        cfg["need"]["recipient_ids"] = [first.pk,named.pk]
        hr.policy(owner,case,AUTHORITY,cfg["authority"],proof["owner"])
        hr.policy(owner,case,DISCLOSURE,cfg["disclosure"],proof["owner"])
        need = hrfinance.need(first,case.pk,"confirmed-recipients",cfg["need"],proof["hr_finance_need"].pk,rev(case))
        contract = hrfinance.contract(first,case.pk,need.pk,"source-contract",proof["hr_contract_source"].pk,rev(case))
        f["contract"] = contract
        hrfinance.decide(owner,case.pk,contract.pk,"approve","approve-recipients",proof["hr_disclosure_decision"].pk,rev(case))
        work = start_station(self,"F35",contract)
        snapshot = hr.capture(f)
        api = f"/api/v1/work/{work.pk}/department-handoff"
        command = api + "/finance-acknowledgement"
        form = {"snapshot_id":snapshot.pk,"revision":rev(case)}
        client = self.client_for(named)
        self.assertContains(client.get(reverse("factory_detail",args=[work.pk])), "Acknowledge HR handoff")
        detail = client.get(api)
        self.assertEqual(detail.json()["finance_acknowledgement"], form)
        self.assertNotContains(detail, "private-staff")
        raw = client.get(reverse("hrfinance_snapshot",args=[case.pk,snapshot.pk]))
        self.assertIn(raw.status_code,(403,404))
        self.assertNotIn(b"private-staff",raw.content)
        prototype = {"action":"acknowledge_finance",**form}
        for key in ("finance_head","hr","admin","ceo","cto","pmo_head","pmo_member"):
            other = self.client_for(users[key])
            self.assertEqual(other.get(api).status_code,404,key)
            self.assertEqual(other.post(command,form,content_type="application/json").status_code,404,key)
            self.assertEqual(other.post(reverse("factory_detail",args=[work.pk]), prototype).status_code,404,key)
        self.assertFalse(contract.records.filter(kind="receipt").exists())
        assert_waiting(self, work)
        form["revision"] = rev(case)
        accepted = client.post(command,form,content_type="application/json")
        self.assertEqual(accepted.status_code,200,accepted.content)
        record = contract.records.get(kind="receipt",actor=named)
        self.assertEqual(accepted.json(),{"receipt_id":record.pk})
        self.assertEqual(client.post(command,form,content_type="application/json").json(),accepted.json())
        self.assertEqual(record.snapshot_id,snapshot.pk)
        self.assertIsNone(client.get(api).json()["finance_acknowledgement"])
        hrfinance.decide(owner,case.pk,contract.pk,"revoke","withdraw-disclosure",proof["hr_disclosure_decision"].pk,rev(case))
        self.assertEqual(client.get(api).status_code,404)
        self.assertEqual(client.post(command,form,content_type="application/json").status_code,404)

    def test_appointed_member_resolves_exact_source_findings_without_granting_a_business_approval(self):
        import json
        from pathlib import Path
        from django.utils import timezone
        from apps.agents import specialist_memory, specialist_packets
        from apps.pmo import planning
        from apps.workflows import factory_progress, native_stations
        from tests.test_engagement_intake import activate as activate_station

        f = planning_helpers.fixture()
        case, actor, subject = f["c"], f["a"], f["packet"]
        users = role_accounts(case)
        reviewer = users["pmo_member"]
        rule = json.loads(Path("fixtures/factory-native-station.json").read_text())
        rule.pop("classification")
        rule["information_resolver_id"] = reviewer.pk
        proof = case.evidence.filter(kind="policy_decision").first()
        activate_station(actor,case,native_stations.COMPONENT,rule,proof)
        work = start_station(self,"P17",subject)
        api = f"/api/v1/work/{work.pk}/department-handoff"
        client = self.client_for(reviewer)
        with patch("adapters.openrouter.completion", return_value={"summary":"The source needs clarification.",
                   "quotes":["1"],"gaps":["Confirm the referenced department."],"assessment":"insufficient"}):
            for _ in range(12):
                type(work.background_progress).objects.filter(work=work).update(available_at=timezone.now())
                factory_progress.run_once(work_id=work.pk)
                while specialist_memory.run_once():
                    pass
                if specialist_packets.review_for(work,reviewer):
                    break
        response = client.get(api)
        self.assertEqual(response.status_code,200,response.content)
        review = response.json()["source_review"]
        self.assertIsNotNone(review)
        self.assertEqual(client.get(review["readings"][0]["report_url"]).status_code,200)
        self.assertContains(client.get(reverse("factory_detail",args=[work.pk])), "Resolve source findings")
        body = {"packet_id":review["packet_id"], "digest":review["digest"], "reason":"Checked the original account."}
        command = api+"/source-review"
        self.assertEqual(self.client_for(actor).post(command,body,content_type="application/json").status_code,404)
        bad = client.post(command,{**body,"digest":"f"*64},content_type="application/json")
        self.assertIn(bad.status_code,(409,422))
        self.assertEqual(self.client_for(users["pmo_head"]).post(command,body,content_type="application/json").status_code,404)
        self.assertEqual(client.post(command,body,content_type="application/json").status_code,200)
        self.assertIsNone(planning.latest(case,"ready"))
        self.assertIsNone(client.get(api).json()["receipt"])
