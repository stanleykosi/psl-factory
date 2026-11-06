from .test_native_invoice_recovery import NativeInvoiceRecoveryTests as Base

class FinanceReadbackRecoveryTests(Base):
    test_archived_four_variants_published_handoff_and_current_source_owner=None
    def test_published_followup_native_readback_review_successors_and_restart(self):
        v,r=self.scenario('followup_setup');v.update(r)
        v.update(readback_key='unknown',configure_readback=True,duplicates=True,review_readback=True)
        unknown=self.child('followup_probe',v);self.assertEqual(unknown['result']['outcome'],'unknown')
        v.pop('configure_readback');v.pop('duplicates');v.pop('review_readback')
        v.update(self.child('source_readback_receive',v));v['readback_key']='acknowledged'
        ack=self.child('followup_probe',v);self.assertEqual(ack['result']['disposition'],'absent')
        self.child('source_accept',v);v.update(readback_key='current',review_readback=True)
        current=self.child('followup_probe',v);self.assertTrue(current['result']['current_authority_verified']);v.pop('review_readback')
        self.child('source_readback_decline',v);v['observation']=current['observation'];self.child('followup_old',v)
        v['readback_key']='declined';declined=self.child('followup_probe',v);self.assertEqual(declined['result']['verdict'],'decline');self.assertTrue(declined['result']['current_authority_verified'])
        self.assertFalse(self.child('source_readback_revoke',v)['decision_current'])
        v['readback_key']='revoked';revoked=self.child('followup_probe',v);self.assertEqual(revoked['result']['outcome'],'acknowledged');self.assertEqual(revoked['result']['disposition'],'revoked')
        v['conflict']=True;self.child('source_readback_receive',v);v['readback_key']='conflict'
        conflict=self.child('followup_probe',v);self.assertEqual(conflict['result']['outcome'],'conflict');self.assertFalse(conflict['result']['financial_effect_verified'])
