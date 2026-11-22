"""Real authenticated pages and API reads for each completed synthetic station."""
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.test import Client
from django.urls import reverse

from apps.workflows.native_station_contracts import registry
from tests.process_role_helpers import role_accounts

# These sources require the department's ordinary read capability. Their
# fixtures have an exact working downstream receipt. A regression that silently
# makes both the domain service and the API reject all staff must fail here.
DEPARTMENT_READS = frozenset("""
    P08 P09 P22 P23 P24 P27 P29 P30 P31 P38 P45 P51 P54 P55 P56 P58 P63
    F02 F04 F05 F06 F08 F10 F11 F14 F15 F19 F24 F25 F26 F27 F28 F32 F33 F34
""".split())


def verify_roles(test, work, received):
    projects = test.__dict__.setdefault("_station_role_projects", {})
    if work.case_id not in projects:
        principals = []
        for key, actor in role_accounts(work.case).items():
            client = Client()
            client.force_login(actor)
            principals.append((key, actor, client))
        projects[work.case_id] = principals

    route = registry()[work.native_station.process]
    model = work.native_station.subject_model
    from django.apps import apps
    source = apps.get_model(model).objects.get(pk=work.native_station.subject_pk)
    read_source = route.observe
    pinned = work.native_station.projection_version
    if pinned != 1:
        revision = route.revised_projection
        read_source = revision.observe if (revision and revision.version == pinned and revision.enabled(source)) else None
    results = {}
    for key, actor, client in projects[work.case_id]:
        expected = False
        own_department = ((route.process.startswith("P") and key.startswith("pmo_"))
                          or (route.process.startswith("F") and key.startswith("finance_")))
        if own_department and read_source is not None:
            try:
                current = read_source(source, actor)
                expected = current.receipt == received
            except (PermissionDenied, ValidationError, ObjectDoesNotExist):
                pass
        public = client.get(f"/api/v1/work/{work.pk}/department-handoff")
        page = client.get(reverse("factory_detail", args=[work.pk]))
        context = f"{route.process}: {key}"
        hr_basis = route.process == "F19" and bool(source.snapshot.get("hr_basis_access"))
        if own_department and read_source is not None and route.process in DEPARTMENT_READS and not hr_basis:
            test.assertTrue(expected, f"Ordinary department read unexpectedly denied for {context}")
        if route.process in {"P05", "F35"}:
            test.assertFalse(expected, f"A recipient-specific receipt reached an unnamed account for {context}")
        test.assertEqual(public.status_code, 200 if expected else 404, context)
        test.assertEqual(any(t.name == "factory/department_handoff.html" for t in page.templates), expected, context)
        if expected:
            test.assertEqual(page.status_code, 200, context)
            test.assertEqual(public.json()["process"], route.process, context)
            test.assertEqual(public.json()["evidence"], list(current.lines.values()), context)
            test.assertIsNotNone(public.json()["receipt"], context)
            test.assertIsNone(public.json()["source_review"], context)
            test.assertIsNone(public.json()["finance_acknowledgement"], context)
            test.assertContains(page, "The receiving record was verified")
            test.assertNotContains(page, "Resolve source findings")
            test.assertNotContains(page, "Acknowledge HR handoff")
        else:
            test.assertEqual(public.json()["code"], "not_found", context)
            test.assertEqual(page.status_code, 404, context)
            test.assertNotIn(b"The receiving record was verified", page.content, context)
        if route.process in {"P02", "P45", "F32", "F35"}:
            prefix = f"/api/v1/work/{work.pk}/department-handoff"
            denied = client.post(prefix + "/source-review", {"packet_id":work.native_station.handoffs.latest("pk").packet_id,
                                 "digest":"f"*64, "reason":"Synthetic terminal-state review"}, content_type="application/json")
            test.assertEqual(denied.status_code,404,context)
            if route.process == "F35":
                denied = client.post(prefix + "/finance-acknowledgement",
                                     {"snapshot_id":received.snapshot_id, "revision":work.case.revision},
                                     content_type="application/json")
                test.assertEqual(denied.status_code,404,context)
        results[key] = "read" if expected else "restricted"
    print("ROLE_ACCESS", route.process, *(f"{key}={result}" for key, result in results.items()), flush=True)
