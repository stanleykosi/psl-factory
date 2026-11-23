"""Deployment contract for reviewed account destinations and an optional delivery relay."""
import json
import os
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.validators import validate_email


@dataclass(frozen=True)
class Route:
    username: str
    email: str
    whatsapp: str
    recovery: bool
    account_id: int | None = None


@dataclass(frozen=True)
class ContactRuntime:
    origin: str
    relay: str
    routes: tuple[Route, ...]
    synthetic: bool


def https_url(value, *, origin_only=False):
    if not isinstance(value, str) or len(value) > 400 or any(char.isspace() for char in value):
        raise ValueError
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.port not in (None, 443) or parsed.query or parsed.fragment
            or (origin_only and parsed.path not in ('', '/'))):
        raise ValueError
    return value.rstrip('/')


def parse(data):
    if not isinstance(data, dict) or data.keys() != {'version', 'origin', 'relay', 'routes'}:
        raise ValueError
    if type(data['version']) is not int or data['version'] != 1:
        raise ValueError
    if not isinstance(data['routes'], list) or not 0 < len(data['routes']) <= 1000:
        raise ValueError
    routes = []
    seen_users = set()
    seen_destinations = set()
    for row in data['routes']:
        if not isinstance(row, dict) or row.keys() != {'account_id', 'username', 'email', 'whatsapp', 'recovery'}:
            raise ValueError
        if (not isinstance(row['username'], str) or not row['username'].strip()
                or len(row['username']) > 150 or row['username'] in seen_users
                or not isinstance(row['email'], str) or len(row['email']) > 254
                or not isinstance(row['whatsapp'], str) or type(row['recovery']) is not bool
                or type(row['account_id']) is not int or row['account_id'] < 1
                or any(route.account_id == row['account_id'] for route in routes)):
            raise ValueError
        validate_email(row['email'])
        if row['whatsapp'] and not re.fullmatch(r'\+[1-9][0-9]{7,14}', row['whatsapp']):
            raise ValueError
        destinations = {row['email'].casefold()} | ({row['whatsapp']} if row['whatsapp'] else set())
        if destinations & seen_destinations:
            raise ValueError
        seen_users.add(row['username'])
        seen_destinations.update(destinations)
        routes.append(Route(**row))
    return ContactRuntime(https_url(data['origin'], origin_only=True), https_url(data['relay']), tuple(routes), False)


def load():
    raw = os.getenv('PSL_CONTACT_DELIVERY_V1')
    if raw:
        try:
            runtime = parse(json.loads(raw))
            secret = os.getenv('PSL_CONTACT_RELAY_TOKEN', '')
            if not re.fullmatch(r'[A-Za-z0-9._~+/-]{16,512}={0,2}', secret):
                raise ValueError
            return runtime
        except (ValueError, ValidationError):
            raise ImproperlyConfigured('Review the account delivery contract and relay credential.') from None
    hostname = 'psl-design-web-design-acceptance.up.railway.app'
    if (os.getenv('RAILWAY_ENVIRONMENT_NAME') == 'design-acceptance'
            and os.getenv('RAILWAY_PROJECT_ID') == 'f957481b-c6f7-43af-bc66-449a330a9d53'):
        return ContactRuntime(f'https://{hostname}', '', (
            Route('psl-agent-trial', 'psl-agent-trial@accounts.invalid', '+12025550123', True),
        ), True)
    return None
