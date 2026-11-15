import re,glob,os
ROOT='/Users/Hunchoo/psl-factory-worktrees/design-start/design/canvas/'
CANV=(('main','project'),('finance','finance/project'))
def files():
  for c,p in CANV:
    for f in sorted(glob.glob(ROOT+p+'/*.dc.html')): yield c,f
def mobile_bar(s):
  mm=re.search(r'<div style="(position: relative; )?width: 390px',s)
  if not mm: return None
  i=mm.start()
  j=s.find('>',i)+1
  m=re.compile(r'<div style="background: #1F2427; color: #FFFFFF; padding: (6px 1[68]px|16px 20px)').search(s,j)
  if not m or m.start()-j>400: return None
  # depth match
  d=0
  for t in re.finditer(r'<(/?)div\b[^>]*>',s[m.start():]):
    d+= -1 if t.group(1) else 1
    if d==0: return (m.start(), m.start()+t.end())
  return None
