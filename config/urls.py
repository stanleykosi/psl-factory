"""Public backend routes and compatibility names for the retired Django pages."""
from django.urls import include, path
from django.urls.resolvers import URLPattern

from apps.agents import upload_views
from apps.core.factory_api.http import error
from apps.documents import template_catalog
from apps.finance import bank_receipt_views, reminder_views
from apps.finance.followup_intake import endpoint as finance_followup_inbox
from apps.pmo import rfp_views
from apps.workflows import factory_invoice_information_views
from legacy_ui.urls import urlpatterns as page_patterns

from .health import health

handler400 = 'apps.core.error_views.bad_request'
handler403 = 'apps.core.error_views.forbidden'
handler404 = 'apps.core.error_views.missing'
handler500 = 'apps.core.error_views.failed'

backend_patterns = [
    path('api/v1/', include('apps.core.factory_api.urls')),
    path('health/', health, name='health'),
    path('finance/followup-inbox/<uuid:case_id>/<str:operation_key>/',
         finance_followup_inbox, name='finance_followup_inbox'),
    # The JSON API returns these authenticated file URLs to clients.
    path('cases/<uuid:case_id>/files/<int:upload_id>/', upload_views.download, name='case_upload_download'),
    path('projects/<uuid:case_id>/templates/<int:template_id>/file/',
         template_catalog.download, name='design_template_download'),
    path('cases/<uuid:case_id>/rfp/intake/<int:intake_id>/attachment/',
         rfp_views.intake_attachment, name='rfp_intake_attachment'),
    path('work/<int:work_id>/invoice-proof/<int:proof_id>/',
         factory_invoice_information_views.download, name='factory_invoice_milestone_proof'),
    path('cases/<uuid:case_id>/finance/invoices/<int:issue_id>/payments/<int:receipt_id>/proof/<str:kind>/',
         bank_receipt_views.download, name='finance_bank_proof'),
    path('cases/<uuid:case_id>/finance/reminders/<int:issue_id>/drafts/<int:draft_id>/<str:file_kind>/',
         reminder_views.download, name='design_reminder_download'),
]


def retired_page(request, **kwargs):
    return error(404, 'page_retired', 'This service provides the PSL Factory API at /api/v1/.')


urlpatterns = backend_patterns + [
    URLPattern(page.pattern, retired_page, default_args=page.default_args, name=page.name)
    for page in page_patterns
]
