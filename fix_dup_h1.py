#!/usr/bin/env python3
"""Dedupe template <h1> titles that were rendered as "Title Title" (the model
emitted the article title twice in a body <h1>, and extract_title lifted the
doubled string into the template <h1>). Only touches attribute-less <h1> (the
template's sole h1) and only when a single space splits it into two EQUAL
halves (left == right, each > 10 chars) — a normal title never matches this,
so the operation is safe and idempotent.

Run with --dry to only report.
"""
import os, re, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'content')
ROOT = os.path.abspath(ROOT)
TPL_H1 = re.compile(r'<h1>(.*?)</h1>', re.S | re.I)


def dedupe(s):
    s = s.strip()
    for i, ch in enumerate(s):
        if ch == ' ':
            left, right = s[:i], s[i + 1:]
            if left == right and len(left) > 10:
                return left
    return s


def main():
    dry = '--dry' in sys.argv
    fixed = 0
    for dp, dn, fn in os.walk(ROOT):
        for f in fn:
            if f != 'index.html':
                continue
            rel = os.path.join(dp, f).replace('\\', '/')
            p = rel.split('/')
            if len(p) < 4 or p[-4] != 'content':
                continue
            t = open(rel, encoding='utf-8').read()
            m = TPL_H1.search(t)
            if not m:
                continue
            orig = m.group(1)
            new = dedupe(orig)
            if new == orig:
                continue
            if dry:
                print('WOULD FIX:', rel)
                print('   ', repr(orig[:120]), '->', repr(new[:120]))
                fixed += 1
                continue
            nt = t[:m.start(1)] + new + t[m.end(1):]
            open(rel, 'w', encoding='utf-8').write(nt)
            fixed += 1
    print(f"{'[DRY-RUN] ' if dry else ''}deduped template h1: {fixed}")


if __name__ == '__main__':
    main()
