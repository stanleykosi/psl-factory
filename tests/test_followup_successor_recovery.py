from .test_native_invoice_recovery import NativeInvoiceRecoveryTests as Base

class FollowupSuccessorRecoveryTests(Base):
    test_archived_four_variants_published_handoff_and_current_source_owner=None
    def test_source_owned_successor_readback_review_and_fresh_process_revocation(self):
        v,r=self.scenario('followup_setup');v.update(r)
        v.update(readback_key='unknown-successors',configure_readback=True,include_successors=True,review_readback=True)
        unknown=self.child('followup_probe',v);self.assertEqual(unknown['result']['outcome'],'unknown');self.assertEqual(unknown['result']['successors']['lineage'],[])
        v.pop('configure_readback');v.pop('review_readback')
        v.update(self.child('source_readback_receive',v));self.child('source_accept',v)
        v.update(self.child('source_readback_lineage',v));v.update(readback_key='current-successors',review_readback=True,duplicates=True)
        current=self.child('followup_probe',v);lineage=current['result']['successors']['lineage'][0]
        self.assertEqual(lineage['status'],'current');self.assertEqual(lineage['successor_receipt'],'present');self.assertFalse(lineage['execution_authorized'])
        v.pop('review_readback');v.pop('duplicates');v['observation']=current['observation']
        revoked=self.child('source_readback_lineage_revoke',v);self.assertEqual(revoked['lineage'][0]['status'],'stale')
        self.child('followup_old',v);v['readback_key']='revoked-successors'
        latest=self.child('followup_probe',v);self.assertEqual(latest['result']['successors']['lineage'][0]['status'],'stale')
        self.assertTrue(latest['result']['current_authority_verified']);self.assertFalse(latest['result']['financial_effect_verified'])
