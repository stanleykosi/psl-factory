from decimal import Decimal,localcontext
from .rules import number,ROUNDING


def compare(actual,budget,prior,method):
    with localcontext() as context:
        context.prec=512;quantum=Decimal(1).scaleb(-method['decimal_places'])
        def rounded(value):return number(value.quantize(quantum,rounding=ROUNDING[method['rounding']]))
        a=None if actual is None else Decimal(actual)
        b=None if budget is None else Decimal(budget)
        p=None if prior is None else Decimal(prior)
        variance=None if a is None or b is None else rounded(a-b)
        prior_variance=None if a is None or p is None else rounded(a-p)
        denominator=None if b is None else abs(b) if method['ratio']=='variance_over_absolute_budget' else b
        numerator=None if a is None else (a-b if b is not None else None) if method['ratio']=='variance_over_absolute_budget' else a
        ratio=None if numerator is None or denominator is None or denominator==0 else rounded(numerator/denominator*Decimal(method['multiplier']))
        return {'value':actual,'budget':budget,'prior':prior,'variance':variance,'prior_variance':prior_variance,'ratio':ratio,
                'ratio_status':'unknown_zero_denominator' if denominator==0 else 'unknown_inputs' if ratio is None else 'known'}
