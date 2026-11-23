"""Versioned private row projection; rejected pay never becomes an eligible zero."""
from collections import defaultdict
from decimal import Decimal,localcontext
import re

from django.core.exceptions import ValidationError
from apps.finance.rules import decimal

IDENTITY=re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}')
BASE={'row_ref','employee_id','component','amount'}


def project(source,request,rules):
    from adapters.payroll import PayrollExportError
    mode=rules['row_handling'];currency_mode=rules['currency_mode']
    if mode not in [None,'reject_export','hold_conflicting_rows'] or currency_mode not in [None,'request_currency','row_currency']:
        raise PayrollExportError('row_rule_scope')
    refs=defaultdict(list);pairs=defaultdict(list);output=[];findings=defaultdict(set)
    for index,row in enumerate(source):
        allowed=BASE|{'currency'} if currency_mode=='row_currency' else BASE
        # An undecided currency source can be captured as held evidence only.
        if currency_mode is None:allowed=BASE|({'currency'} if isinstance(row,dict) and 'currency' in row else set())
        allowed_sets=[allowed,BASE] if currency_mode=='row_currency' else [allowed]
        if not isinstance(row,dict) or set(row) not in allowed_sets:raise PayrollExportError('out_of_contract_fields')
        if any(not isinstance(row[key],str) or not IDENTITY.fullmatch(row[key]) for key in ['row_ref','employee_id','component']):
            raise PayrollExportError('identity_schema')
        if row['component'] not in rules['allowed_components']:raise PayrollExportError('component_scope')
        if row['amount'] is not None:
            try:
                value=decimal(row['amount'])
                with localcontext() as ctx:
                    ctx.prec=512
                    rounded=value.quantize(Decimal(1).scaleb(-rules['source_decimal_places']))
                if value!=rounded:raise ValueError
            except (ValidationError,ValueError,ArithmeticError):raise PayrollExportError('amount_schema_or_precision')
        if currency_mode is None:findings[index].add('row_currency_rule_unconfigured')
        elif currency_mode=='row_currency':
            currency=row.get('currency')
            if currency in (None,''):findings[index].add('missing_row_currency')
            elif not isinstance(currency,str) or not IDENTITY.fullmatch(currency):findings[index].add('invalid_row_currency')
            elif currency!=request.metadata['currency']:findings[index].add('row_currency_mismatch')
        refs[row['row_ref']].append(index);pairs[(row['employee_id'],row['component'])].append(index)
        output.append({key:row[key] for key in BASE}|{'data_row':index+1})
    for group in list(refs.values())+list(pairs.values()):
        if len(group)>1:
            for index in group:findings[index].add('duplicate_source_row_or_component')
    codes=set()
    for index,row in enumerate(output):
        issues=findings[index]
        if not issues:continue
        if mode=='reject_export':raise PayrollExportError(sorted(issues)[0])
        if mode is None:issues.add('row_handling_rule_unconfigured')
        # Keep the exact allowed source amount for human inspection; arithmetic
        # receives unknown for the entire conflicting pay item, never a zero.
        row.update(source_amount=row['amount'],amount=None,quarantine_codes=sorted(issues))
        currency=source[index].get('currency')
        if 'currency' in source[index]:
            row['source_currency']=currency if isinstance(currency,str) and IDENTITY.fullmatch(currency) else None
        codes.update(issues)
    return output,{'protocol':'psl.payroll-row-projection/v2','source_rows':len(source),
                   'held_rows':sum(bool(row.get('quarantine_codes')) for row in output),'codes':sorted(codes)}
