import os, re
ROOT = 'content'
files = []
for dp, dn, fn in os.walk(ROOT):
    for f in fn:
        if f != 'index.html':
            continue
        files.append(os.path.join(dp, f).replace('\\', '/'))
bad_multi = 0
bad_dup = 0
for p in files:
    t = open(p, encoding='utf-8').read()
    h1s = re.findall(r'<h1[^>]*>(.*?)</h1>', t, re.S | re.I)
    if len(h1s) != 1:
        bad_multi += 1
    for h in h1s:
        s = h.strip()
        for i, ch in enumerate(s):
            if ch == ' ' and s[:i] == s[i+1:] and len(s[:i]) > 10:
                bad_dup += 1
                break
print('files:', len(files))
print('files with !=1 h1:', bad_multi)
print('files with residual space-split double h1:', bad_dup)
