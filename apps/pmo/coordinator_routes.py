"""Process-specific native entry points for the PMO release."""
from .coordinator_changes import ROUTES as changes
from .coordinator_commercial import ROUTES as commercial
from .coordinator_delivery import ROUTES as delivery
from .coordinator_documents import ROUTES as documents
from .coordinator_visibility import ROUTES as visibility

ROUTES = (*commercial, *delivery, *documents, *changes, *visibility)
