"""Diagnose Key Takeaways health across all articles.

Three defect classes:
  A. MISSING   - no <section class="key-takeaways"> at all
  B. DUPLICATE - more than one Key Takeaways block in one article
  C. MISPLACED - the section sits inside an illegal/flow-broken parent
                 (<p>, <td>, <th>, <li>, <blockquote>, <h2>...) which
                 corrupts the HTML structure.

Prints compact counts + sample slugs. Usage: python audit_kt.py [detail]
"""
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'content')
KT_RE = re.compile(r'<section class="key-takeaways"[^>]*>.*?</section>', re.S | re.I)
CS_START = '<!-- COMMUNITY-SECTION-START -->'

# tags that may legally contain a <section>
BAD_PARENTS = ('p', 'td', 'th', 'li', 'blockquote', 'h1', 'h2', 'h3', 'a', 'strong', 'em', 'span')


def articles():
    out = []
    for dp, dn, fn in os.walk(ROOT):
        for f in fn:
            if f != 'index.html':
                continue
            rel = os.path.join(dp, f).replace('\\', '/')
            parts = rel.split('/')
            if len(parts) >= 4 and parts[-4] == 'content':
                out.append(rel)
    return out


def detect_bad_parent(text, kt_start):
    """Illegal ancestor of the KT block, resolved by one authoritative source:
    normalize_kt.open_stack / closer_tags. A per-tag regex cannot tell a closed
    pair from an unclosed opener and produces false positives here.
    """
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import normalize_kt as N

        need = N.closer_tags(text[:kt_start])
        return need[-1] if need else None
    except Exception:
        return None


def main():
    detail = 'detail' in sys.argv
    files = articles()
    missing, dup, bad = [], [], []
    for rel in files:
        t = open(rel, encoding='utf-8').read()
        blocks = list(KT_RE.finditer(t))
        if not blocks:
            missing.append(rel)
            continue
        if len(blocks) > 1:
            dup.append((rel, len(blocks)))
        for b in blocks:
            tag = detect_bad_parent(t, b.start())
            if tag:
                bad.append((rel, tag, len(blocks)))
                break

    total = len(files)
    slug = lambda r: '/'.join(r.split('/')[-3:-1])
    print('=== KEY TAKEAWAYS HEALTH ===')
    print(f'articles total        : {total}')
    print(f'  missing  KT (A)     : {len(missing)}')
    print(f'  duplicate KT (B)    : {len(dup)}')
    print(f'  misplaced KT (C)    : {len(bad)}   <- HTML structure broken')
    ok = total - len(missing) - len({r for r, _, _ in bad} - {r for r in missing})
    print(f'  clean (has KT, well-placed): {ok}')
    if detail:
        print('\n--- [A] MISSING KT ---')
        for r in missing:
            print('  ', slug(r))
        print('\n--- [B] DUPLICATE KT ---')
        for r, n in dup:
            print(f'   x{n}  {slug(r)}')
        print('\n--- [C] MISPLACED KT (template part + use this URL form) ---')
        for r, tag, n in bad:
            print(f'   <{tag}> x{n}  {r}')
    else:
        print('\n(samples)')
        for r in missing[:5]:
            print('   [A]', slug(r))
        for r, n in dup[:5]:
            print(f'   [B] x{n} {slug(r)}')
        for r, tag, n in bad[:8]:
            print(f'   [C] <{tag}> x{n} {slug(r)}')


if __name__ == '__main__':
    main()
