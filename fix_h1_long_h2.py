#!/usr/bin/env python3
"""One-off: fix two residual heading defects across 821224 content:

  1. h1 x2  -> remove every <h1> that lives inside the article body region
               (between <div class="article-content"> and the COMMUNITY marker).
               The template already renders the single, correct <h1>{{title}}</h1>
               OUTSIDE that region, so stripping body h1 is always safe.
  2. long / prose headings -> convert non-styled <h2>/<h3> whose text is either
               multi-sentence prose OR longer than 160 chars into <p> (the text is
               preserved; only the tag changes). Styled headings (Key Takeaways /
               Comments) are left untouched.

Idempotent. Run with --dry to only report.
"""
import os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'generate'))
from fix_h2_structure import is_multi_sentence, raw_text

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'content')
ROOT = os.path.abspath(ROOT)
AC_OPEN = '<div class="article-content">'
CS_MARK = '<!-- COMMUNITY-SECTION-START -->'
H1 = re.compile(r'<h1[^>]*>.*?</h1>', re.S | re.I)
HEAD = re.compile(r'<h([23])([^>]*)>(.*?)</h\1>', re.S | re.I)
LEN_LIMIT = 160


def fix_body_region(body):
    # 1) strip stray h1 entirely
    h1_removed = len(H1.findall(body))
    body = H1.sub('', body)
    # 2) convert over-long / prose headings to <p>
    out = []
    last = 0
    changed = 0
    for m in HEAD.finditer(body):
        out.append(body[last:m.start()])
        tag, attrs, inner = m.group(1).lower(), m.group(2), m.group(3)
        raw = raw_text(inner)
        if 'style=' in attrs.lower():
            out.append(body[m.start():m.end()])
        elif is_multi_sentence(raw) or len(raw) > LEN_LIMIT:
            out.append('<p>' + inner + '</p>')
            changed += 1
        else:
            out.append(body[m.start():m.end()])
        last = m.end()
    out.append(body[last:])
    return ''.join(out), h1_removed, changed


def process(rel, dry):
    t = open(rel, encoding='utf-8').read()
    ac = t.find(AC_OPEN)
    if ac == -1:
        return None
    ac += len(AC_OPEN)
    cs = t.find(CS_MARK)
    cs = len(t) if cs == -1 else cs
    body = t[ac:cs]
    new_body, h1r, h2c = fix_body_region(body)
    if new_body == body:
        return None
    if not dry:
        open(rel, 'w', encoding='utf-8').write(t[:ac] + new_body + t[cs:])
    return (h1r, h2c)


def main():
    dry = '--dry' in sys.argv
    files = []
    for dp, dn, fn in os.walk(ROOT):
        for f in fn:
            if f != 'index.html':
                continue
            rel = os.path.join(dp, f).replace('\\', '/')
            p = rel.split('/')
            if len(p) >= 4 and p[-4] == 'content':
                files.append(rel)
    tot_h1 = tot_h2 = changed_files = 0
    for rel in files:
        r = process(rel, dry)
        if r:
            changed_files += 1
            tot_h1 += r[0]
            tot_h2 += r[1]
    print(f"{'[DRY-RUN] ' if dry else ''}scanned: {len(files)}, changed: {changed_files}")
    print(f"  body <h1> removed (fixes h1 x2): {tot_h1}")
    print(f"  over-long/prose heading -> <p>  : {tot_h2}")


if __name__ == '__main__':
    main()
