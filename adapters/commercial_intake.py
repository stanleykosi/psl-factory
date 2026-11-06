"""A private reference bundle, not another costing model or approval."""
from adapters.forecast import obj
from adapters.costing import read

KIND='agent_private_commercial_intake'
PROTOCOL='factory-commercial-intake/v1'
ID={'anyOf':[{'type':'integer','minimum':1},{'type':'null'}]}
FIELDS=['requirements','plan','engineering_estimate','security_estimate','sow','inputs','rule_id','oracle_id','template_id','predecessor_id','context_id']
VALUE=obj({key:ID for key in FIELDS})
PACKET=obj({'protocol':{'const':PROTOCOL},'sources':VALUE})

class CommercialIntakeAdapter:
    def read(self,evidence):return read(evidence.body,PACKET)
