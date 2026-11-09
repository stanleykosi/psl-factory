"""Explicit local synthetic P56 extraction. No network or business commands."""
import re

FIELDS={'reference':['cr id','change reference'], 'requestor':['requestor','requested by'],
    'date_raised':['date raised'], 'module':['affected module','module'],
    'description':['description','change description'], 'reason':['reason']}

class SyntheticChangeIntakeProvider:
    name='synthetic-p56-extraction-v1'
    def extract(self,text):
        fields={};questions=[]
        for name,labels in FIELDS.items():
            matches=[]
            for line in text.splitlines():
                for label in labels:
                    match=re.fullmatch(r'\s*'+re.escape(label)+r'\s*:\s*(\S.*)\s*',line,re.I)
                    if match:matches.append((match.group(1).strip(),line))
            distinct={v for v,q in matches}
            if len(distinct)==1:
                value,quote=matches[0];fields[name]={'value':value,'quote':quote}
            else:
                fields[name]={'value':None,'quote':None}
                questions.append(('Clarify conflicting ' if matches else 'Supply ')+name.replace('_',' '))
        categories=[]
        for line in text.splitlines():
            match=re.fullmatch(r'\s*(?:suggested )?category\s*:\s*(Standard|Normal|Emergency)\s*',line,re.I)
            if match:categories.append((match.group(1).capitalize(),line))
        if len({v for v,q in categories})==1:
            value,quote=categories[0];category={'suggestion':value,'quote':quote}
        else:
            category={'suggestion':None,'quote':None};questions.append('PM must classify the change; no category is assumed')
        return {'fields':fields,'category':category,'questions':questions}
