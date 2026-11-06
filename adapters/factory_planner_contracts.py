"""Engineering gateway protocol and independent public planning canary."""
PROTOCOL='psl.factory-planner/v1'
DATA_SCOPE='eligible_actions_and_opaque_citations_v1'
CANARY_RESULT={'activity':'ACT04','citations':['probe0']}

def canary_payload(model_id):
    return {'protocol':PROTOCOL,'model_id':model_id,'data_scope':DATA_SCOPE,'eligible':['ACT04'],
        'citation_handles':['probe0'],'tools':[],'token_limit':100,'max_output_chars':512}
