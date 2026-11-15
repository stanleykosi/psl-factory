#!/usr/bin/env python3
"""Insert the board's own phone "+ Start" into the top bar of phone boards that lack it. usage: start.py [--apply]"""
import sys,csv,json
sys.path.insert(0,'/private/tmp/claude-501/design-start')
from lib import *
APPLY='--apply' in sys.argv
MAIN_URL='https://claude.ai/artifact/THB9steET1h8qCmZp9jdD2'
SVG='<svg aria-hidden="true" width="12" height="12" viewBox="0 0 14 14"><path d="M7 1v12M1 7h12" stroke="currentColor" stroke-width="2.4"/></svg>'
STY='min-height: 44px; display: inline-flex; align-items: center; gap: 6px; padding: 0 14px; background: #C8401C; color: #FFFFFF; font-weight: 600; text-decoration: none; white-space: nowrap;'
def start(cv):
  if cv=='main': return '<a href="SCR-04-mobile.dc.html" data-cmp="CMP-23" style="%s">%sStart</a>'%(STY,SVG)
  return '<a href="%s" target="_blank" data-cmp="CMP-23" style="%s">%sStart</a>'%(MAIN_URL,STY,SVG)
WRAP='<span style="display: inline-flex; align-items: center; gap: 12px;">'
MONO=re.compile(r'<span style="font-family: \'IBM Plex Mono\', monospace; font-size: 12px;">[^<]*</span>')
def skip_reason(name):
  n=name[:-8]
  if n=='Main': return 'pointer'
  if n.endswith('-concepts') or re.match(r'[a-d]-',n) or n.startswith('mascot'): return 'concept'
  if n.startswith('LINE') : return 'reference line flow (not a platform screen)'
  if n.endswith('-flow-desktop') or n=='FINANCE-moved-desktop': return 'flow overview'
  if n.startswith('SCR-17'): return 'signed-out page (no session, no Start)'
  if 'whatsapp' in n: return 'WhatsApp message mock (not an app screen)'
  return None
rows=[]; 
for cv,f in files():
  name=os.path.basename(f); s=open(f).read()
  pw=re.search(r'"\$preview":\{"width":(\d+)',s); width=pw.group(1) if pw else ''
  had='data-cmp="CMP-23"' in s
  sk=skip_reason(name); var=''; changed=False
  if sk: var='skip: '+sk
  elif '<div style="width: 390px' in s or '<div style="position: relative; width: 390px' in s:
    b=mobile_bar(s)
    if not b: var='UNCLASSIFIED phone'
    else:
      bar=s[b[0]:b[1]]
      if 'data-cmp="CMP-23"' in bar: var='phone wordmark bar'
      elif re.search(r'<a [^>]*>← ',bar):
        has_note=bool(MONO.search(bar))
        var='phone back-link bar'+(' + page word' if has_note else ' (no page word)')
        if not had:
          nb=bar
          if has_note:
            m=list(MONO.finditer(nb))[-1]
            nb=nb[:m.start()]+WRAP+m.group(0)+start(cv)+'</span>'+nb[m.end():]
          else:
            nb=nb[:-6]+start(cv)+'</div>'
            if 'justify-content' not in nb[:200]:
              nb=re.sub(r'^(<div style="[^"]*?)(display: flex; )?(align-items: center;)?"',lambda m:m.group(1)+'display: flex; justify-content: space-between; align-items: center;"',nb,count=1)
          s=s[:b[0]]+nb+s[b[1]:]; changed=True
      else: var='UNCLASSIFIED phone'
  elif '<nav aria-label="Main" style="background: #1F2427' in s:
    var='desktop top bar (nav)'
  else: var='UNCLASSIFIED'
  if changed and APPLY: open(f,'w').write(s)
  rows.append((name,cv,width,var,'yes' if had else 'no','yes' if changed else 'no'))
os.makedirs('/Users/Hunchoo/psl-factory/delivery/design-start-in-top-bar',exist_ok=True)
with open('/Users/Hunchoo/psl-factory/delivery/design-start-in-top-bar/survey.csv','w',newline='') as o:
  w=csv.writer(o); w.writerow(['board','canvas','width','variant','had_start','changed']); w.writerows(rows)
import collections
print(collections.Counter((r[1],r[3],r[5]) for r in rows).most_common())
print([r[:4] for r in rows if 'UNCLASS' in r[3]])
json.dump([(r[1],r[0]) for r in rows if r[5]=='yes'],open('/private/tmp/claude-501/design-start/changed.json','w'))
