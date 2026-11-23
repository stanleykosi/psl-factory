"""URL configuration for running the archived pages locally."""
from config.urls import backend_patterns, handler400, handler403, handler404, handler500

from .urls import urlpatterns as page_patterns

urlpatterns = backend_patterns + page_patterns
