"""Bounded supported pricing method; no invented rates, tiers, tax or FX."""
from decimal import Decimal,localcontext
from .rules import decimal,number,ROUNDING
from django.core.exceptions import ValidationError

def price(quantity,rate,method):
    if quantity is None:return {'net':None,'tax':None,'total':None,'raw_net':None}
    with localcontext() as c:
        c.prec=512
        q=decimal(quantity,nonnegative=True);r=decimal(rate,nonnegative=True)
        quantum=Decimal(1).scaleb(-method['decimal_places']);rounding=ROUNDING[method['rounding']]
        raw=q*r
        net=raw.quantize(quantum,rounding=rounding)
        tax=(net*decimal(method['tax_rate'],nonnegative=True)).quantize(quantum,rounding=rounding)
        gross=net+tax
        if abs(gross)>=Decimal('1e24'):raise ValidationError('Pricing numeric budget exceeded')
        return {'net':number(net),'tax':number(tax),'total':number(gross),'raw_net':number(raw)}
