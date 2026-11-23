"""Opaque access-request acknowledgement. No work lookup is performed."""
from apps.identity.work_access_views import access_requested, record_access_request

from .http import BOOLEAN, Problem, endpoint, obj


RESPONSE = obj({'requested': BOOLEAN})


@endpoint(response=RESPONSE, summary='Read your own access-request acknowledgement for a work reference')
def status(http, work_id):
    return {'requested': access_requested(http.user, work_id)}


@endpoint(method='POST', request=obj({}), response=RESPONSE,
          summary='Request access to a work reference without disclosing its existence')
def request_access(http, work_id, *, body):
    del body
    if not record_access_request(http.user, work_id):
        raise Problem(429, 'rate_limited', 'Wait before requesting access to another work item.')
    return {'requested': True}
