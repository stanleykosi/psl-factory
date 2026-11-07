"""Bounded hosted Intuit MCP client. Discovery is untrusted; no write capability."""
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from http.client import HTTPException
from jsonschema import Draft202012Validator

URL = 'https://mcp.quickbooks.intuit.com/mcp'
VERSION = '2025-11-25'
READ_TOOL = 'qbo_sales_get_invoices'
READ_SCOPE = 'sales.tools.invoice.read'
LIMIT = 131072

class MCPError(Exception):
    """Sanitized failure: callers must not infer success or replay an unknown call."""


def require(ok):
    if not ok:
        raise MCPError('Unsupported or invalid MCP contract')


def pairs(items):
    out = {}
    for key, value in items:
        require(key not in out)
        out[key] = value
    return out


def bounded(value, limit=LIMIT):
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        require(len(encoded) <= limit)
        return encoded
    except (ValueError, TypeError, RecursionError):
        raise MCPError('Invalid bounded MCP value') from None


def decode(raw):
    require(isinstance(raw, bytes) and len(raw) <= LIMIT)
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(MCPError('Nonfinite MCP value')))
    except (ValueError, TypeError, RecursionError):
        raise MCPError('Invalid bounded MCP response') from None


def fingerprint(value):
    return hashlib.sha256(bounded(value)).hexdigest()


def schema_check(schema, depth=0):
    # A deliberately bounded supported subset. No remote refs, regex execution,
    # dynamic evaluation, format resolution or unbounded recursive schemas.
    require(isinstance(schema, dict) and depth <= 12)
    allowed = {'type','properties','required','additionalProperties','items','enum','const',
               'minItems','maxItems','minLength','maxLength','minimum','maximum','description','title'}
    require(set(schema) <= allowed and schema.get('type') in ['object','array','string','integer','number','boolean','null'])
    if schema['type'] == 'object':
        require(schema.get('additionalProperties') is False and isinstance(schema.get('properties'), dict) and len(schema['properties']) <= 64)
        for key, child in schema['properties'].items():
            require(isinstance(key, str) and 0 < len(key) <= 100)
            schema_check(child, depth+1)
    if schema['type'] == 'array':
        require(type(schema.get('maxItems')) is int and 0 <= schema['maxItems'] <= 100)
        schema_check(schema.get('items'), depth+1)
    if schema['type'] == 'string':
        require(type(schema.get('maxLength')) is int and 0 <= schema['maxLength'] <= 4096)
    try:
        Draft202012Validator.check_schema(schema)
    except Exception:
        raise MCPError('Unsupported MCP schema') from None


def validate(schema, value):
    schema_check(schema)
    bounded(value, 16384)
    require(not any(Draft202012Validator(schema).iter_errors(value)))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def transport(token, app_name, body, notification=False):
    require(isinstance(token, str) and 0 < len(token) <= 4096 and all(32 < ord(c) < 127 for c in token))
    require(isinstance(app_name, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,60}', app_name))
    request = urllib.request.Request(URL, data=bounded(body), method='POST', headers={
        'Authorization':'Bearer '+token, 'User-Agent':'partner_app_'+app_name,
        'Content-Type':'application/json', 'Accept':'application/json, text/event-stream',
        'MCP-Protocol-Version':VERSION})
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(request, timeout=5) as response:
            require(response.headers.get('Mcp-Session-Id') is None)
            # Validate status before consuming a stream. Notifications never have
            # a JSON-RPC response ID and require an empty 202 response.
            require(response.status == (202 if notification else 200))
            content_type = response.headers.get_content_type()
            if not notification:
                require(content_type in ('application/json', 'text/event-stream') and 'id' in body)
            raw = b''
            deadline = time.monotonic()+5
            while True:
                require(time.monotonic() <= deadline)
                chunk = response.read1(min(4096, LIMIT+1-len(raw)))
                if not chunk:
                    break
                raw += chunk
                require(len(raw) <= LIMIT)
                if notification:
                    raise MCPError('MCP notification response must be empty')
                if content_type == 'text/event-stream':
                    # A heartbeat or stream priming event is not a reply. Parse
                    # only complete events, retaining split UTF-8/CRLF/data.
                    normalized = raw.replace(b'\r\n', b'\n')
                    boundary = normalized.rfind(b'\n\n')
                    if boundary >= 0:
                        result = stream_response(normalized[:boundary+2], body['id'])
                        if result is not None:
                            return result
            if notification:
                return None
            return parse_response(raw, content_type, body['id'])
    except urllib.error.HTTPError as exc:
        code = exc.code
        exc.close()
        raise MCPError('MCP throttled' if code == 429 else 'MCP authentication rejected' if code in (401,403) else 'MCP transport unknown') from None
    except (OSError, TimeoutError, HTTPException):
        raise MCPError('MCP transport unknown') from None


def rpc_result(value, request_id):
    # No server-initiated requests, notifications or mismatched replies.
    require(isinstance(value, dict) and value.get('jsonrpc') == '2.0' and type(value.get('id')) is type(request_id) and value.get('id') == request_id)
    require(set(value) in ({'jsonrpc','id','result'}, {'jsonrpc','id','error'}))
    if 'error' in value:
        raise MCPError('MCP remote error')
    require(isinstance(value['result'], dict))
    return value['result']


def stream_response(raw, request_id):
    require(isinstance(raw, bytes) and len(raw) <= LIMIT)
    try:
        text = raw.decode('utf-8').replace('\r\n','\n')
    except UnicodeError:
        raise MCPError('Invalid MCP stream') from None
    require(text.endswith('\n\n'))
    events = text.split('\n\n')[:-1]
    require(len(events) <= 64)
    messages = []
    for event in events:
        data = []
        event_type = 'message'
        for line in event.split('\n'):
            if line.startswith(':') or not line:
                continue
            key, _, value = line.partition(':')
            value = value.removeprefix(' ')
            if key == 'event':
                event_type = value or 'message'
            elif key == 'data':
                data.append(value)
            elif key == 'id':
                # Valid SSE metadata, never a JSON-RPC correlation ID. We do
                # not reconnect, persist credentials, or replay using this ID.
                require(len(value) <= 512 and '\x00' not in value)
            elif key == 'retry':
                require(value.isascii() and value.isdigit() and len(value) <= 8)
            # SSE ignores unknown fields. They cannot become RPC instructions.
        payload = '\n'.join(data)
        if payload:
            require(event_type == 'message')
            messages.append(decode(payload.encode()))
    require(len(messages) <= 1)
    return rpc_result(messages[0], request_id) if messages else None


def parse_response(raw, content_type, request_id):
    if content_type == 'application/json':
        return rpc_result(decode(raw), request_id)
    if content_type == 'text/event-stream':
        result = stream_response(raw, request_id)
        require(result is not None)
        return result
    raise MCPError('Unsupported MCP response type')


class Client:
    def __init__(self, token, app_name):
        self.token, self.app_name, self.number = token, app_name, 0
        self.ready = False

    def request(self, method, params):
        self.number += 1
        return transport(self.token, self.app_name, {'jsonrpc':'2.0','id':self.number,'method':method,'params':params})

    def initialize(self):
        result = self.request('initialize', {'protocolVersion':VERSION,'capabilities':{},
            'clientInfo':{'name':'psl-qbo-read-broker','version':'1'}})
        require(result.get('protocolVersion') == VERSION and isinstance(result.get('capabilities'), dict)
            and isinstance(result['capabilities'].get('tools'), dict) and isinstance(result.get('serverInfo'), dict))
        transport(self.token, self.app_name, {'jsonrpc':'2.0','method':'notifications/initialized'}, True)
        self.ready = True

    def discover(self):
        require(self.ready)
        tools, seen, cursor = [], set(), None
        for _ in range(4):
            result = self.request('tools/list', {} if cursor is None else {'cursor':cursor})
            require(set(result) <= {'tools','nextCursor','_meta'} and isinstance(result.get('tools'), list))
            for item in result['tools']:
                require(isinstance(item, dict) and isinstance(item.get('name'), str)
                    and re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', item['name']) and isinstance(item.get('inputSchema'), dict))
                require(item['name'] not in {t['name'] for t in tools})
                bounded(item, 32768)
                tools.append(item)
                require(len(tools) <= 64)
            cursor = result.get('nextCursor')
            if cursor is None:
                bounded(tools)
                return tools
            require(isinstance(cursor, str) and 0 < len(cursor) <= 512 and cursor not in seen)
            seen.add(cursor)
        raise MCPError('MCP discovery pagination limit')

    def call(self, reviewed_tool, arguments, output_schema):
        require(self.ready and reviewed_tool.get('name') == READ_TOOL)
        validate(reviewed_tool.get('inputSchema'), arguments)
        schema_check(output_schema)
        current = [item for item in self.discover() if item['name'] == READ_TOOL]
        require(len(current) == 1 and fingerprint(current[0]) == fingerprint(reviewed_tool))
        result = self.request('tools/call', {'name':READ_TOOL,'arguments':arguments})
        require(result.get('isError', False) is False and isinstance(result.get('structuredContent'), dict))
        validate(output_schema, result['structuredContent'])
        # Text, resources and prompts never enter the result projection.
        return result['structuredContent']
