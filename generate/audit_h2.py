import os, re, sys, html, subprocess
sys.path.insert(0, os.path.dirname(__file__))
import fix_h2_structure as F

root = '821224.com/content'
files = []
for dp, dn, fn in os.walk(root):
    for f in fn:
        if f != 'index.html':
            continue
        rel = os.path.join(dp, f).replace('\\', '/')
        p = rel.split('/')
        if len(p) >= 4 and p[-4] == 'content':
            files.append(rel)

def norm(s):
    s = re.sub(r'<[^>]+>', '', s); s = html.unescape(s).strip().lower()
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', '', s)).strip()

dup = prose = degenerate = 0
deg_files = []
kt_now = comm_now = tbl_now = 0
kt_head = comm_head = tbl_head = 0
for rel in files:
    t = open(rel, encoding='utf-8').read()
    if 'class="key-takeaways"' in t: kt_now += 1
    if 'COMMUNITY-SECTION-START' in t: comm_now += 1
    if '<table' in t: tbl_now += 1
    gitpath = rel[len('821224.com/'):]  # repo root is inside 821224.com/
    h = subprocess.run(['git', '-C', '821224.com', 'show', f'HEAD:{gitpath}'],
                       capture_output=True, text=True).stdout
    if 'class="key-takeaways"' in h: kt_head += 1
    if 'COMMUNITY-SECTION-START' in h: comm_head += 1
    if '<table' in h: tbl_head += 1
    m = re.search(r'<h1[^>]*>(.*?)</h1>', t, re.S | re.I)
    title = norm(m.group(1)) if m else ''
    ac = t.find('<div class="article-content">')
    if ac == -1:
        continue
    ac += len('<div class="article-content">')
    cs = t.find('<!-- COMMUNITY-SECTION-START -->')
    cs = len(t) if cs == -1 else cs
    body = t[ac:cs]
    h2 = h3 = 0
    for l, attrs, x in F.HEAD_RE.findall(body):
        if 'style=' in attrs.lower():
            if l == '2': h2 += 1
            continue
        raw = F.raw_text(x); nrm = norm(raw)
        if l == '2':
            h2 += 1
            if title and nrm == title: dup += 1
            if F.is_multi_sentence(raw): prose += 1
        else:
            h3 += 1
    if h2 == 0 and h3 == 0:
        degenerate += 1; deg_files.append(rel.split('/')[-2])

dm = sum(1 for rel in files if open(rel, encoding='utf-8').read().count('COMMUNITY-SECTION-START') > 1)

print('=== FINAL AUDIT ===')
print('residual dup-title h2 :', dup)
print('residual prose h2     :', prose)
print('degenerate(0h2&0h3)   :', degenerate, deg_files[:10])
print('KT   now/HEAD:', kt_now, '/', kt_head)
print('comm now/HEAD:', comm_now, '/', comm_head)
print('tbl  now/HEAD:', tbl_now, '/', tbl_head)
print('files >1 community marker:', dm)
