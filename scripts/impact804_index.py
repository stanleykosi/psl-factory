"""Lossless deterministic encoding of new804 proof only. Never writes Git state."""
import gzip,hashlib,json
from pathlib import Path

def fingerprint(raw):
    return {'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}

def write_index(path,raw):
    path=Path(path);meta=Path(str(path)+'.json')
    if path.exists() or meta.exists():raise RuntimeError('Unique new index proof required')
    encoded=gzip.compress(raw,mtime=0)
    if gzip.decompress(encoded)!=raw:raise RuntimeError('Index encoding roundtrip failed')
    with path.open('xb') as f:f.write(encoded)
    with meta.open('x') as f:json.dump(fingerprint(raw),f,sort_keys=True);f.write('\n')

def read_index(path):
    path=Path(path)
    raw=gzip.decompress(path.read_bytes())
    if fingerprint(raw)!=json.loads(Path(str(path)+'.json').read_text()):raise RuntimeError('Index proof fingerprint mismatch')
    return raw

def equal_index(path,raw):
    if read_index(path)!=raw:raise RuntimeError('Tracked index identity changed')
