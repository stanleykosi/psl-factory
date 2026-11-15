# usage: python3 missing.py <outroot> [filter] : missing (not excepted) board items per board
import json, os, sys, re
root = sys.argv[1]; flt = sys.argv[2] if len(sys.argv) > 2 else '.'
for d in sorted(os.listdir(root)):
    p = os.path.join(root, d, 'report.json')
    if not os.path.exists(p) or not re.search(flt, d): continue
    r = json.load(open(p)); c = r['coverage']
    miss = [m for m in c['missing'] if not m.get('exception')]
    print(f"== {d} visual={r['scores']['visual']} cov={r['scores']['coverageWithExceptions']}")
    for m in miss: print('   ', m['role'], '|', m.get('name'))
