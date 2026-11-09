"""PostgreSQL workbench paging, bounded transfer and exact command regressions."""
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.core.models import Evidence
from apps.core.services import add_evidence
from apps.documents import template_current as current, template_lists as lists
from apps.documents.controlled import register_template
from apps.documents.models import Template, TemplateClaim, TemplateResolution, TemplateScope
from apps.identity.models import Grant
from .document_helpers import DEFINITION
from .helpers import rev, setup_case
from .test_template_current import configure, scope


class TemplateWorkbenchListTests(TestCase):
    def setUp(self):
        self.actor, self.case = setup_case()
        self.policy = add_evidence(self.actor, self.case.pk, 'policy_decision', 'Synthetic decision', 'synthetic:policy')
        self.template = register_template(self.actor, self.case.pk, 'Early template', DEFINITION, self.policy.pk, rev(self.case))
        self.scope = scope(self.actor, self.case, self.policy, document_type='status_report')
        self.url = reverse('template_current', args=(self.case.pk,))
        self.client.force_login(self.actor)

    def test_large_inventory_pages_and_exact_off_page_form_submission(self):
        with CaptureQueriesContext(connection) as small:
            self.assertContains(self.client.get(self.url), 'Owner template claims')
        TemplateScope.objects.bulk_create([
            TemplateScope(case=self.case, document_type='status_report', audience='client', purpose=f'Synthetic purpose {i}',
                          context='Exact project', source_owner='Synthetic owner', evidence=self.policy, actor=self.actor)
            for i in range(80)
        ])
        Evidence.objects.bulk_create([
            Evidence(case=self.case, kind=current.SOURCE_KIND, version=i + 1, body='PRIVATE LARGE BODY' * 300,
                     source=f'synthetic:list-{i}', sha256='0' * 64, created_by=self.actor)
            for i in range(160)
        ])
        Template.objects.bulk_create([
            Template(case=self.case, name=f'Template {i}', version=1, evidence=self.policy,
                     definition=DEFINITION, created_by=self.actor)
            for i in range(120)
        ])
        with CaptureQueriesContext(connection) as large:
            page = self.client.get(self.url)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(len(page.context['rows']), lists.SCOPE_PAGE)
        self.assertEqual(len(page.context['sources']), lists.LIST_PAGE)
        self.assertEqual(len(page.context['templates']), lists.LIST_PAGE)
        self.assertEqual(len(large), len(small))
        print(f'Workbench list rehearsal: {len(small)} SQL queries for both small and large inventories')
        self.assertFalse(any('"core_evidence"."body"' in entry['sql'] for entry in large.captured_queries))
        self.assertNotContains(page, 'PRIVATE LARGE BODY')
        self.assertNotContains(page, 'Early template')
        for key, items in [('scopes', 'scopes'), ('sources', 'sources'), ('templates', 'templates')]:
            with self.subTest(section=key):
                subsequent = self.client.get(self.url + page.context[f'more_{key}'])
                self.assertEqual(subsequent.status_code, 200)
                self.assertTrue({row.pk for row in page.context[items]}.isdisjoint(
                    row.pk for row in subsequent.context[items]
                ))
        self.assertEqual(self.client.get(self.url, {'scopes': 'tampered'}).status_code, 400)
        response = self.client.post(self.url, {
            'action': 'claim', 'revision': rev(self.case), 'scope': self.scope.pk,
            'evidence': self.policy.pk, 'template': self.template.pk, 'note': 'Off-page exact records',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(TemplateClaim.objects.filter(scope=self.scope, template=self.template, evidence=self.policy).exists())

    def test_history_pages_keep_complete_resolution_review_separate(self):
        policy = configure(self.actor, self.case, self.policy, [self.template], [(self.scope, self.actor)])
        history = TemplateClaim.objects.bulk_create([
            TemplateClaim(scope=self.scope, template=self.template, actor=self.actor,
                          evidence=self.policy, note=f'Synthetic claim {i}')
            for i in range(40)
        ])
        ids = [row.pk for row in history]
        TemplateResolution.objects.bulk_create([
            TemplateResolution(scope=self.scope, selected_claim=history[0], claim_ids=ids,
                               evidence=self.policy, actor=self.actor, owner_policy=policy, note=f'Historical decision {i}')
            for i in range(32)
        ])
        main = self.client.get(self.url)
        self.assertContains(main, 'Review complete current claims')
        self.assertEqual(len(main.context['scopes'][0].shown_claims), lists.HISTORY_PREVIEW)
        self.assertEqual(len(main.context['scopes'][0].shown_decisions), lists.HISTORY_PREVIEW)
        self.assertNotContains(main, 'Synthetic claim 0')
        self.assertNotContains(main, 'name="claim_ids"')
        with CaptureQueriesContext(connection) as queries:
            focus = self.client.get(self.url, {'scope': self.scope.pk})
        self.assertEqual(len(focus.context['scopes'][0].shown_claims), lists.LIST_PAGE)
        self.assertEqual(len(focus.context['scopes'][0].shown_decisions), lists.LIST_PAGE)
        self.assertFalse(any('"documents_templateresolution"."claim_ids"' in entry['sql'] for entry in queries.captured_queries))
        self.assertContains(self.client.get(self.url + focus.context['more_claims']), 'Synthetic claim 0')
        self.assertContains(self.client.get(self.url + focus.context['more_decisions']), 'Historical decision 0')
        complete = self.client.get(self.url, {'scope': self.scope.pk, 'review': '1'})
        self.assertEqual(complete.context['rows'][0][1]['status'], 'CURRENT')
        self.assertEqual(json.loads(complete.context['rows'][0][1]['claim_ids_json']), ids)

    def test_paged_visibility_and_cursor_binding(self):
        private = TemplateScope.objects.create(case=self.case, document_type='finance_report', audience='internal',
            purpose='PRIVATE FINANCE SCOPE', context='Restricted', source_owner='Synthetic', evidence=self.policy, actor=self.actor)
        observer = get_user_model().objects.create_user(username='list-observer')
        for action in ('case.read', 'document.read'):
            Grant.objects.create(case=self.case, user=observer, action=action)
        with patch.object(lists, 'SCOPE_PAGE', 1):
            page = self.client.get(self.url)
        cursor = page.context['more_scopes']
        self.client.force_login(observer)
        self.assertEqual(self.client.get(self.url + cursor).status_code, 400)
        self.assertEqual(self.client.get(self.url, {'scopes': 'x' * 513}).status_code, 400)
        self.assertEqual(self.client.get(self.url, {'scope': private.pk}).status_code, 404)
        self.assertNotContains(self.client.get(self.url), 'PRIVATE FINANCE SCOPE')
        with patch.object(lists, 'LIST_QUERY_LIMIT', 1):
            self.assertContains(self.client.get(self.url), 'This page could not be opened', status_code=503)
