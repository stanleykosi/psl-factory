"""Synthetic component regressions only: no DB, sockets, live tokens or providers."""
import copy
import json
import unittest
from unittest.mock import patch, MagicMock
from adapters import quickbooks_mcp as m, quickbooks_online as q

TOKEN='synthetic-echo-"\\-only'
INPUT={'type':'object','properties':{'id':{'type':'string','maxLength':30}},'required':['id'],'additionalProperties':False}
TOOL={'name':m.READ_TOOL,'inputSchema':INPUT}
OUTPUT={'type':'object','properties':{'id':{'type':'string','maxLength':30},'note':{'type':'string','maxLength':100}},'required':['id','note'],'additionalProperties':False}

class SecretEchoTests(unittest.TestCase):
    def test_decoded_nested_values_keys_and_escaping_are_rejected(self):
        for value in [{'text':'prefix '+TOKEN+' suffix'},{'nested':[{TOKEN:'value'}]}]:
            raw=json.dumps(value).encode();decoded=m.decode(raw)
            with self.assertRaises(m.MCPError) as e:m.reject_bearer_echo(decoded,TOKEN)
            self.assertNotIn(TOKEN,str(e.exception))
        self.assertEqual(m.reject_bearer_echo({'value':'ordinary'},TOKEN),{'value':'ordinary'})

    def test_discovery_rejects_token_description_before_return(self):
        client=m.Client(TOKEN,'fixture');client.ready=True
        with patch.object(client,'request',return_value={'tools':[dict(TOOL,description=TOKEN)]}):
            with self.assertRaises(m.MCPError):client.discover()

    def test_projection_rejects_token_even_when_schema_valid(self):
        client=m.Client(TOKEN,'fixture');client.ready=True
        with patch.object(client,'discover',return_value=[TOOL]),patch.object(client,'request',return_value={'structuredContent':{'id':'42','note':TOKEN}}):
            with self.assertRaises(m.MCPError):client.call(TOOL,{'id':'42'},OUTPUT)

    def test_successful_projection_is_unchanged(self):
        client=m.Client(TOKEN,'fixture');client.ready=True;value={'id':'42','note':'ordinary'}
        with patch.object(client,'discover',return_value=[TOOL]),patch.object(client,'request',return_value={'structuredContent':value}):
            self.assertEqual(client.call(TOOL,{'id':'42'},OUTPUT),value)

    def test_request_boundary_rejects_echo_before_any_consumer(self):
        client=m.Client(TOKEN,'fixture')
        with patch.object(m,'transport',return_value={'serverInfo':{'name':TOKEN}}):
            with self.assertRaises(m.MCPError):client.request('initialize',{})

class BodyBudgetTests(unittest.TestCase):
    URL='https://sandbox-quickbooks.api.intuit.com/v3/company/123/invoice/42?minorversion=75'
    def response(self,chunks):
        result=MagicMock();result.status=200;result.headers.get_content_type.return_value='application/json'
        result.__enter__.return_value=result;result.read1.side_effect=chunks
        return result

    def test_chunked_read_preserves_body_and_caps_each_request(self):
        result=self.response([b'{',b'}',b''])
        with patch.object(q.urllib.request,'build_opener') as opener,patch.object(q.time,'monotonic',return_value=0):
            opener.return_value.open.return_value=result
            self.assertEqual(q.transport(self.URL,'synthetic')[2],b'{}')
        self.assertTrue(all(0<x.args[0]<=q.READ_CHUNK for x in result.read1.call_args_list))
        result.read.assert_not_called();result.__exit__.assert_called_once()

    def test_post_read_budget_prevents_accepting_late_eof(self):
        result=self.response([b''])
        with patch.object(q.urllib.request,'build_opener') as opener,patch.object(q.time,'monotonic',side_effect=[0,0,6]):
            opener.return_value.open.return_value=result
            with self.assertRaises(TimeoutError):q.transport(self.URL,'synthetic')
            opener.return_value.open.assert_called_once()
        result.__exit__.assert_called_once()

    def test_drip_reaching_budget_stops_without_next_read(self):
        result=self.response([b'{',b'"'])
        with patch.object(q.urllib.request,'build_opener') as opener,patch.object(q.time,'monotonic',side_effect=[0,0,2,4,6]):
            opener.return_value.open.return_value=result
            with self.assertRaises(TimeoutError):q.transport(self.URL,'synthetic')
        self.assertEqual(result.read1.call_count,2)

    def test_oversize_returns_only_limit_plus_one_for_protocol_rejection(self):
        result=self.response([b'x'*q.READ_CHUNK]*16+[b'x'])
        with patch.object(q.urllib.request,'build_opener') as opener,patch.object(q.time,'monotonic',return_value=0):
            opener.return_value.open.return_value=result
            self.assertEqual(len(q.transport(self.URL,'synthetic')[2]),q.MAX_BODY+1)
        self.assertEqual(result.read1.call_args.args,(1,))

class BrokerProjectionTests(unittest.TestCase):
    def function(self,name,env):
        import ast
        from pathlib import Path
        tree=ast.parse((Path(__file__).resolve().parents[1]/'apps/workflows/quickbooks_mcp.py').read_text())
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
        self.assertEqual(node.decorator_list,[])
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<exact MCP broker>', 'exec'),env)
        return env[name]

    def test_real_execute_records_unknown_not_echoed_projection(self):
        from types import SimpleNamespace
        from django.core.exceptions import ValidationError
        from unittest.mock import Mock
        entry={'app_name':'fixture','reviewed_tool':TOOL,'output_schema':OUTPUT,'result_identity_key':'id'}
        stored={'arguments':{'id':'42'},'target':'42'}
        finish=Mock(return_value='retained-unknown')
        env={'connection':SimpleNamespace(in_atomic_block=False,get_autocommit=lambda:True),'ValidationError':ValidationError,
             'claim':Mock(return_value=(stored,{'entry':entry,'secret':TOKEN})),'Client':m.Client,'MCPError':m.MCPError,'finish':finish}
        execute=self.function('execute',env)
        with patch.object(m.Client,'initialize',lambda c:setattr(c,'ready',True)),patch.object(m.Client,'discover',return_value=[TOOL]),patch.object(m.Client,'request',return_value={'structuredContent':{'id':'42','note':TOKEN}}):
            self.assertEqual(execute('actor','case',1),'retained-unknown')
        self.assertEqual(finish.call_args.args[-1],{'status':'unknown','projection':None})
        self.assertNotIn(TOKEN,repr(finish.call_args))

    def test_real_probe_sanitizes_echo_without_discovery_payload(self):
        from types import SimpleNamespace
        from django.core.exceptions import ValidationError
        from unittest.mock import Mock
        public={'pin':'synthetic'}
        env={'binding':Mock(return_value=(public,{'entry':{'app_name':'fixture'},'secret':TOKEN})),
             'Client':m.Client,'MCPError':m.MCPError,'ValidationError':ValidationError}
        probe=self.function('probe',env)
        job=SimpleNamespace(intent={'kind':'health','binding':public},contract=object())
        with patch.object(m.Client,'initialize',lambda c:setattr(c,'ready',True)),patch.object(m.Client,'request',return_value={'tools':[dict(TOOL,description=TOKEN)]}):
            with self.assertRaises(ConnectionError) as e:probe(job)
        self.assertNotIn(TOKEN,str(e.exception))
