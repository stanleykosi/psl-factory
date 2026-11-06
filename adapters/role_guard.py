"""Native authority evaluation only; cannot approve a business action or create grants."""
from apps.identity.services import require
from apps.policy.services import decision_authority,resolve
from apps.policy.role_assignments import report,authorize_header


def required(arguments):
    values=['D05.role_principal_assignments']
    if arguments['delegated']:values.append('D05.delegation_rules')
    if arguments['decision_action']!='approve':values.append('D05.decision_action_matrix')
    return values


def guard(actor,case,role,decision_action,delegated):
    require(actor,case,'case.read')
    authority=decision_authority(actor,case,role,decision_action,delegated)
    return None,{'authority':authority,'role':role,'decision_action':decision_action,'delegated':delegated,
        'authority_scope':'role_and_decision_action_only','action_authority_granted':False,'business_approval':False},None


def readable(observer,case,arguments):
    value=report(observer,case.pk)
    for component in required(arguments):authorize_header(observer,case,component)
    return value


def head(observer,case,user_id,arguments):
    value=readable(observer,case,arguments)
    return {'nomination_status':value['status'],'configuration':value.get('configuration'),
        'role':arguments['role'],'decision_action':arguments['decision_action'],'delegated':arguments['delegated'],
        'selected_person':next((r for r in value['assignments'] if r['user_id']==user_id),None),
        'required_policies':[{'component':key,'status':resolve(key,case).status} for key in required(arguments)],
        'action_grants_evaluated':False,'independence_controls_waived':False,'business_approval':False}
