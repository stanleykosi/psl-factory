"""Source identity shared by early process startup and native archive compatibility."""
import hashlib,json


def identity(root):
    files={}
    for directory in ['apps','adapters','config','templates','contracts']:
        for path in sorted((root/directory).rglob('*')):
            if path==root/'contracts/implementation-coverage.json':continue
            if path.is_file() and path.suffix in ['.py','.json','.html']:
                files[path.relative_to(root).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    files['requirements.lock']=hashlib.sha256((root/'requirements.lock').read_bytes()).hexdigest()
    return hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
