"""Exact full raw snapshot comparison, including sequence state; no database access."""
import gzip
import json
import sys
with gzip.open(sys.argv[1],'rt') as source:before=json.load(source)
with gzip.open(sys.argv[2],'rt') as source:after=json.load(source)
if before!=after:raise RuntimeError('Full raw snapshot equality failed')
print('Exact raw snapshot equality including sequences PASS')
