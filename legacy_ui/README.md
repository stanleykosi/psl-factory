# Archived Django frontend

`templates/`, `static/` and `urls.py` contain the original server-rendered pages, assets and page routes. Railway uses the API-only route configuration in [`config/urls.py`](../config/urls.py). The old page names still generate reference links for existing API responses, while requests to those pages receive a JSON 404. The signed Finance inbox and API-linked private downloads have their own backend routes.

For local comparison or Django page regression tests, run with `PSL_DJANGO_UI=1`. Use `PSL_DJANGO_UI=0` to run the backend as it runs on Railway. Some shared forms and helpers remain in `apps/` because API handlers use their validation and permission logic.

Build the replacement in [`frontend/`](../frontend/) using the [Next.js handoff](../handoffs/nextjs/README.md).
