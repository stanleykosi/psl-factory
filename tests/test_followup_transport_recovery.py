import os,sys,json,subprocess,base64
from .test_native_invoice_recovery import NativeInvoiceRecoveryTests as Base

class FollowupTransportRecoveryTests(Base):
    test_archived_four_variants_published_handoff_and_current_source_owner=None
    def test_signed_current_source_intake_uncertain_response_receipt_first_recovery(self):
        v,r=self.scenario('followup_setup');v.update(r);v['transport_secret']=base64.b64encode(os.urandom(32)).decode()
        env=os.environ.copy();env.update(PGDATABASE=v['provider_database'],DJANGO_SETTINGS_MODULE='config.settings')
        server=subprocess.Popen([sys.executable,'-m','tests.finance_followup_server'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            server.stdin.write(json.dumps(v)+'\n');server.stdin.flush();line=server.stdout.readline()
            if not line:raise AssertionError('Source inbox startup failed: '+server.stderr.read())
            v.update(json.loads(line));v.update(self.child('transport_prepare',v))
            uncertain=self.child('transport_uncertain',v);self.assertEqual(uncertain['status'],'unknown')
            v.update(self.child('source_readback_transport_revoke',v))
            confirmed=self.child('transport_reconcile',v);self.assertEqual(confirmed['status'],'confirmed');self.assertFalse(confirmed['financial_effect_verified'])
            v.update(readback_key='after-authenticated-intake',configure_readback=True,review_readback=True)
            readback=self.child('followup_probe',v);self.assertEqual(readback['result']['outcome'],'acknowledged');self.assertEqual(readback['result']['disposition'],'absent')
        finally:
            if server.poll() is None:
                server.stdin.write('stop\n');server.stdin.flush()
            _,err=server.communicate(timeout=30)
            self.assertEqual(server.returncode,0,err)
