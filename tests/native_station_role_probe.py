"""Real authenticated pages and API reads for each completed synthetic station."""
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.test import Client
from django.urls import reverse

from apps.workflows.native_station_contracts import registry
from tests.process_role_helpers import role_accounts


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
    results = {}
    for key, actor, client in projects[work.case_id]:
        expected = False
        if (route.process.startswith("P") and key.startswith("pmo_")) or (
                route.process.startswith("F") and key.startswith("finance_")):
            try:
                current = route.observe(source, actor)
                expected = current.receipt == received
            except (PermissionDenied, ValidationError, ObjectDoesNotExist):
                pass
        public = client.get(f"/api/v1/work/{work.pk}/department-handoff")
        page = client.get(reverse("factory_detail", args=[work.pk]))
        with test.subTest(process=route.process, role=key):
            test.assertEqual(public.status_code, 200 if expected else 404)
            test.assertEqual(any(t.name == "factory/department_handoff.html" for t in page.templates), expected)
            if expected:
                test.assertEqual(page.status_code, 200)
                test.assertEqual(public.json()["process"], route.process)
                test.assertEqual(public.json()["evidence"], list(current.lines.values()))
                test.assertIsNotNone(public.json()["receipt"])
                test.assertContains(page, "The receiving record was verified")
            else:
                test.assertEqual(public.json()["code"], "not_found")
                test.assertNotIn(b"The receiving record was verified", page.content)
        results[key] = "read" if expected else "restricted"
    print("ROLE_ACCESS", route.process, *(f"{key}={result}" for key, result in results.items()), flush=True)
