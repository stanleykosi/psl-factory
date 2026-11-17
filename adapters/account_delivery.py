"""One bounded send and exact receipt lookup through a reviewed HTTPS relay."""
import json
import os
import re
from urllib.error import URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def receipt_for(runtime, operation, fingerprint, *, payload=None):
    secret = os.getenv('PSL_CONTACT_RELAY_TOKEN', '')
    if not secret:
        return None
    request = Request(f'{runtime.relay}/{operation}', method='PUT' if payload else 'GET',
                      data=json.dumps(payload).encode() if payload else None, headers={
                          'Authorization': f'Bearer {secret}', 'Content-Type': 'application/json',
                          'Accept': 'application/json',
                      })
    try:
        with build_opener(NoRedirect()).open(request, timeout=8) as response:
            raw = response.read(4097)
        result = json.loads(raw) if len(raw) <= 4096 else None
    except (URLError, OSError, ValueError):
        return None
    if (isinstance(result, dict) and result.keys() == {'operation', 'fingerprint', 'state', 'receipt'}
            and result['operation'] == str(operation) and result['fingerprint'] == fingerprint
            and result['state'] == 'delivered' and isinstance(result['receipt'], str)
            and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', result['receipt'])):
        return result['receipt']
    return None
