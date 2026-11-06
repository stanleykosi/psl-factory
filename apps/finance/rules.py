"""Reviewed finite Decimal algorithms. Configuration supplies accounting choices."""
from decimal import Decimal,InvalidOperation,localcontext,ROUND_HALF_EVEN,ROUND_HALF_UP,ROUND_DOWN
from django.core.exceptions import ValidationError

ROUNDING={'half_even':ROUND_HALF_EVEN,'half_up':ROUND_HALF_UP,'down':ROUND_DOWN}

def decimal(value,*,nonnegative=False,positive=False):
    if not isinstance(value,str) or len(value)>64:raise ValidationError('Exact decimal strings are required')
    try:
        n=Decimal(value)
        if not n.is_finite() or abs(n)>=Decimal('1e24') or n.as_tuple().exponent < -8 or (nonnegative and n<0) or (positive and n<=0):raise InvalidOperation
    except (InvalidOperation,ValueError):raise ValidationError('Finite bounded exact decimal required (maximum eight fractional places)')
    return n

def number(n):return None if n is None else format(n,'f')

def total(values):
    values=list(values)
    if not values or any(v is None for v in values):return None
    with localcontext() as c:
        c.prec=512
        return sum((Decimal(v) for v in values),Decimal(0))

def evaluate(rule,operands):
    """No eval, spreadsheet execution, network calls or implicit missing-to-zero."""
    with localcontext() as c:
        c.prec=512
        if any(operands.get((t['kind'],t['key'])) is None for t in rule['terms']):
            return {'value':None,'unrounded':None,'rounding_difference':None,'unit':rule['output_unit'],'status':'unknown'}
        try:
            numerator=sum((Decimal(operands[(t['kind'],t['key'])])*decimal(t['coefficient']) for t in rule['terms']),Decimal(0))
            raw=numerator/decimal(rule['divisor'],positive=True)
            rounded=raw.quantize(Decimal(1).scaleb(-rule['decimal_places']),rounding=ROUNDING[rule['rounding']])
            if abs(raw)>=Decimal('1e24'):raise InvalidOperation
        except (InvalidOperation,KeyError,ZeroDivisionError):raise ValidationError('Formula numeric budget or operand contract exceeded')
        return {'value':number(rounded),'unrounded':number(raw),'rounding_difference':number(raw-rounded),'unit':rule['output_unit'],'status':'known'}

def formula_order(rules):
    by_key={r['key']:r for r in rules}
    if len(by_key)!=len(rules):raise ValidationError('Formula keys must be unique')
    order=[];visiting=set();depths={}
    def visit(key):
        if key in visiting:raise ValidationError('Formula graph is cyclic or exceeds 30 dependency levels')
        if key not in by_key:raise ValidationError('Unknown formula dependency: '+key)
        if key in depths:return depths[key]
        visiting.add(key);depth=0
        for term in by_key[key]['terms']:
            if term['kind']=='formula':
                depth=max(depth,1+visit(term['key']))
                if by_key[key]['scope']=='company_and_bu' and by_key[term['key']]['scope']=='company_only':raise ValidationError('A BU formula cannot depend on a company-only output')
                if by_key[term['key']]['output_unit']!='major_currency':raise ValidationError('Formula dependencies must use base currency; presentation scaling occurs once')
        if depth>30:raise ValidationError('Formula graph is cyclic or exceeds 30 dependency levels')
        visiting.remove(key);depths[key]=depth;order.append(by_key[key]);return depth
    for key in by_key:visit(key)
    return order

def proportional(amount,weights,rule):
    with localcontext() as c:
        c.prec=512;quantum=Decimal(1).scaleb(-rule['decimal_places'])
        if amount!=amount.quantize(quantum):raise ValidationError('Source amount exceeds configured allocation precision; no implicit source rounding')
        denominator=sum(weights.values(),Decimal(0))
        if denominator<=0:raise ValidationError('Allocation denominator is zero or unknown')
        allocations={bu:(amount*w/denominator).quantize(quantum,rounding=ROUNDING[rule['rounding']]) for bu,w in sorted(weights.items())}
        residual=amount-sum(allocations.values(),Decimal(0))
        if rule['residual']=='assign_to_configured_bu':
            bu=rule['residual_bu']
            if bu not in weights:raise ValidationError('Residual destination must be an eligible BU')
            allocations[bu]+=residual;residual=Decimal(0)
        return allocations,residual,denominator
