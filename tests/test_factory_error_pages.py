from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import Client, SimpleTestCase, override_settings
from django.urls import path

from config.urls import handler403, handler404, handler500, urlpatterns as application_urls


def forbidden(request):
    raise PermissionDenied('Synthetic private source diagnostic.')


def failed(request):
    raise RuntimeError('Synthetic private provider diagnostic.')


def form(request):
    return HttpResponse('Synthetic action processed.')


urlpatterns = application_urls + [
    path('synthetic-access-error/', forbidden),
    path('synthetic-service-error/', failed),
    path('synthetic-form/', form),
]


@override_settings(ROOT_URLCONF=__name__, DEBUG=False)
class FactoryErrorPageTests(SimpleTestCase):
    def test_forbidden_and_missing_pages_keep_status_style_and_diagnostic_privacy(self):
        response = self.client.get('/synthetic-access-error/', secure=True)
        self.assertContains(response, 'Access needs review', status_code=403)
        self.assertNotContains(response, 'Synthetic private source diagnostic.', status_code=403)
        self.assertEqual(response['Cache-Control'], 'no-store')
        response = self.client.get('/synthetic-page-that-does-not-exist/', secure=True)
        self.assertContains(response, 'Page unavailable', status_code=404)
        self.assertContains(response, 'factory-design.css', status_code=404)
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_service_failure_and_expired_form_keep_native_security_controls(self):
        self.client.raise_request_exception = False
        response = self.client.get('/synthetic-service-error/', secure=True)
        self.assertContains(response, 'There was a problem loading this page', status_code=500)
        self.assertNotContains(response, 'Synthetic private provider diagnostic.', status_code=500)
        self.assertEqual(response['Cache-Control'], 'no-store')
        client = Client(enforce_csrf_checks=True)
        response = client.post('/synthetic-form/', {'action': 'synthetic'}, secure=True)
        self.assertContains(response, 'Reopen this page', status_code=403)
        self.assertNotContains(response, 'Synthetic action processed.', status_code=403)
        self.assertEqual(response['Cache-Control'], 'no-store')
