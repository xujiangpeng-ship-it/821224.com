#!/usr/bin/env python3
"""Normalize Key Takeaways blocks across the whole site.

Three defect classes handled here:
  A. MISSING   -> generate a Key Takeaways block with the LLM
  B. DUPLICATE -> keep only the single best existing block
  C. MISPLACED -> block sits inside <p>/<td>/<th>/<li>/... because the article
                  has unclosed flow tags right before the community marker.
                  We close those tags before inserting, restoring valid HTML.
  D. DEGRADED  -> existing block has <3 bullets, or a bullet is truncated
                  (e.g. ends with ':' ; shorter than 40 chars) -> regenerate.

Idempotent: re-running never duplicates or moves an already-correct block.
Checkpoint file .kt_done.txt lets a killed run resume.

Usage:
  python normalize_kt.py --dry     # report only
  python normalize_kt.py           # fix everything
  python normalize_kt.py --limit N # only process N articles (LLM budget)
"""
import html
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', 'content')
CHECKPOINT = os.path.join(HERE, '..', '.kt_done.txt')

CS_START = '<!-- COMMUNITY-SECTION-START -->'
AC_OPEN = '<div class="article-content">'
# Insertion anchors, best first: right before the community block, else right
# before the comments block. Both sit at a legal top-level position.
ANCHORS = [
    '<!-- COMMUNITY-SECTION-START -->',
    '<!-- COMMENTS -->',
    '<div id="comments"',
]
KT_RE = re.compile(r'<section class="key-takeaways"[^>]*>.*?</section>', re.S | re.I)
LI_RE = re.compile(r'<li[^>]*>(.*?)</li>', re.S | re.I)

KT_STYLE = 'background:#fff;border:1px solid #E2E8F0;border-radius:12px;padding:24px 28px 18px;margin:36px 0 8px;'
KT_OPEN = (
    '            <section class="key-takeaways" style="%s">\n'
    '            <h2 style="font-size:1.15rem;font-weight:700;color:#0B1121;'
    'margin-bottom:12px;letter-spacing:-0.01em;">Key Takeaways</h2>\n'
    '            <ul style="margin:0;padding-left:20px;color:#1E293B;'
    'line-height:1.85;font-size:0.95rem;">\n'
) % KT_STYLE
KT_CLOSE = '            </ul>\n        </section>'

VOID = {'br', 'img', 'hr', 'input', 'meta', 'link', 'source', 'col', 'wbr'}
TAG_RE = re.compile(r'<(/?)([a-zA-Z][a-zA-Z0-9]*)([^>]*?)(/?)>', re.S)
# Tags that are a safe *direct* parent for a <section>. Anything else that is
# still unclosed right before the anchor gets closed first, so the block can
# never end up nested inside a paragraph, table cell or list item.
# Note: <td>/<th> are deliberately NOT listed — a Key Takeaways card dropped
# into a table cell is legal HTML but useless to a reader and to crawlers.
CONTAINER_OK = {'html', 'body', 'article', 'div', 'main', 'section'}

LLM_SYSTEM = (
    "You are a senior editor at an insurance-technology trade publication.\n"
    "You write Key Takeaways blocks for busy claims/insurance executives.\n"
    "Rules you never break:\n"
    "1. Every bullet must be one complete, self-contained sentence.\n"
    "2. Cite at least one concrete number, percentage, vendor name, or time "
    "frame when the article contains one.\n"
    "3. No hype, no 'in today's fast-paced world', no 'it's important to note', "
    "no 'game-changer', no rhetorical questions.\n"
    "4. No markdown formatting. Plain sentences only.\n"
    "5. Return exactly the bullets, one per line, each starting with '- '."
)
LLM_USER = (
    "Write 4 Key Takeaways for the article below.\n\n"
    "ARTICLE TITLE: {title}\n\n"
    "ARTICLE BODY:\n{body}\n\n"
    "Return 4 lines, each starting with '- '. Each line: 15-40 words, one "
    "complete sentence, concrete and specific to THIS article."
)


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
    return sorted(out)


def open_stack(head):
    """Tags still unclosed at the end of `head` (outermost first)."""
    stack = []
    for m in TAG_RE.finditer(head):
        closing, name = m.group(1) == '/', m.group(2).lower()
        if name in VOID or name in ('!doctype',):
            continue
        if m.group(4) == '/':
            continue
        if closing:
            for i in range(len(stack) - 1, -1, -1):
                if stack[i] == name:
                    del stack[i:]
                    break
        else:
            stack.append(name)
    return stack


def closer_tags(head):
    """Tags to close so an inserted <section> lands at a legal position."""
    stack = open_stack(head)
    need = []
    for name in reversed(stack):
        if name in CONTAINER_OK:
            break
        need.append(name)
    return need


def bullets_of(kt_html):
    out = []
    for m in LI_RE.finditer(kt_html):
        t = html.unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip()
        if t:
            out.append(t)
    return out


def score(kt_html):
    """Higher is better. Negative => unusable."""
    bs = bullets_of(kt_html)
    if len(bs) < 3:
        return -1
    for b in bs:
        if len(b) < 40 or b.rstrip().endswith(':'):
            return -1
    return sum(len(b) for b in bs)


def plain_text(fragment, limit=6000):
    t = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', fragment, flags=re.S | re.I)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = html.unescape(t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t[:limit]


def llm_available():
    return bool(os.environ.get('AGNES_API_KEY', '').strip())


_client = None


def get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(
            base_url=os.environ.get('AGNES_BASE_URL', 'https://apihub.agnes-ai.com/v1'),
            api_key=os.environ['AGNES_API_KEY'].strip(),
            timeout=120,
        )
    return _client


def generate_bullets(title, body, retries=3):
    """Return list of bullet strings, or [] on failure."""
    for attempt in range(retries):
        try:
            r = get_client().chat.completions.create(
                model=os.environ.get('AGNES_MODEL', 'agnes-3.0-flash'),
                messages=[
                    {'role': 'system', 'content': LLM_SYSTEM},
                    {'role': 'user', 'content': LLM_USER.format(
                        title=title, body=body)},
                ],
                temperature=0.4,
                max_tokens=700,
            )
            raw = (r.choices[0].message.content or '').strip()
            lines = [l.strip()[2:].strip() for l in raw.splitlines()
                     if l.strip().startswith('- ')]
            lines = [l for l in lines if len(l) > 30]
            if len(lines) >= 3:
                return lines[:5]
        except Exception as e:
            msg = str(e)
            wait = 25 * (attempt + 1) if '429' in msg else 5
            sys.stderr.write('    LLM %s -> wait %ds\n' % (msg[:70], wait))
            time.sleep(wait)
    return []


def build_kt(bullets):
    body = ''.join('            <li>%s</li>\n' % html.escape(b) for b in bullets)
    return KT_OPEN + body + KT_CLOSE


def title_of(text):
    m = re.search(r'<h1[^>]*>(.*?)</h1>', text, re.S | re.I)
    if not m:
        return ''
    return html.unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip()


def find_anchor_pos(text):
    """Index of the preferred insertion anchor, or -1."""
    for a in ANCHORS:
        i = text.find(a)
        if i != -1:
            return i
    return -1


def body_region(text):
    i = text.find(AC_OPEN)
    start = i + len(AC_OPEN) if i != -1 else 0
    at = find_anchor_pos(text)
    end = at if at != -1 else len(text)
    return start, end


def process(rel, dry, stats):
    text = open(rel, encoding='utf-8').read()
    existing = list(KT_RE.finditer(text))
    best, best_score = None, -2
    for m in existing:
        s = score(m.group(0))
        if s > best_score:
            best, best_score = m.group(0), s

    if existing:
        stats['has'] += 1
        if len(existing) > 1:
            stats['dup'] += 1
    else:
        stats['missing'] += 1

    kept_bullets = bullets_of(best) if (best and best_score > 0) else []
    if kept_bullets:
        stats['keep'] += 1
    else:
        stats['regen'] += 1

    # ---- strip every existing KT block ----
    cleaned = KT_RE.sub('', text)
    at = find_anchor_pos(cleaned)
    if at == -1:
        stats['no_marker'] += 1
        return None

    need_close = closer_tags(cleaned[:at])
    if need_close:
        stats['close'] += 1

    bullets = kept_bullets
    if not bullets:
        if not llm_available():
            stats['skipped_no_llm'] += 1
            return None
        start, end = body_region(text)
        bullets = generate_bullets(title_of(text), plain_text(text[start:end]))
        if not bullets:
            stats['llm_failed'] += 1
            return None
        stats['llm_ok'] += 1

    kt = build_kt(bullets)
    prefix = ''.join('</%s>' % t for t in need_close)
    new = cleaned[:at] + prefix + '\n' + kt + '\n\n' + cleaned[at:]

    # collapse a table that became empty once the stray block was lifted out
    new = re.sub(r'<table>\s*<thead>\s*<tr>\s*<th>\s*</th>\s*</tr>\s*</thead>\s*</table>\s*',
                 '', new, flags=re.I)

    if dry:
        return {'changed': True} if new != text else None
    if new != text:
        open(rel, 'w', encoding='utf-8').write(new)
        return {'changed': True}
    return None


def main():
    dry = '--dry' in sys.argv
    limit = None
    for i, a in enumerate(sys.argv):
        if a == '--limit' and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    done = set()
    if os.path.exists(CHECKPOINT):
        done = set(l.strip() for l in open(CHECKPOINT, encoding='utf-8') if l.strip())

    files = articles()
    todo = [f for f in files if f not in done]
    if limit:
        todo = todo[:limit]

    stats = dict(has=0, missing=0, dup=0, keep=0, regen=0, close=0,
                 llm_ok=0, llm_failed=0, no_marker=0, skipped_no_llm=0)
    changed = 0
    cpf = open(CHECKPOINT, 'a', encoding='utf-8')
    for n, rel in enumerate(todo, 1):
        try:
            r = process(rel, dry, stats)
            if r and r.get('changed'):
                changed += 1
        except Exception as e:
            sys.stderr.write('  ERROR %s: %s\n' % (rel.split('/')[-2], str(e)[:160]))
        if not dry:
            cpf.write(rel + '\n')
            cpf.flush()
        if n % 20 == 0:
            print('  ... %d/%d processed (changed %d, llm %d)' % (n, len(todo), changed, stats['llm_ok']))
    cpf.close()

    print('\n%s=== KT NORMALIZE ===' % ('[DRY] ' if dry else ''))
    print('  processed            : %d (checkpoint-skipped %d)' % (len(todo), len(done)))
    print('  already had KT       : %d   (duplicated: %d)' % (stats['has'], stats['dup']))
    print('  missing KT -> generate: %d' % stats['missing'])
    print('  kept existing bullets: %d' % stats['keep'])
    print('  regenerated (degraded): %d' % stats['regen'])
    print('  repaired misplacement : %d' % stats['close'])
    print('  LLM calls ok/failed   : %d / %d' % (stats['llm_ok'], stats['llm_failed']))
    print('  no community marker   : %d' % stats['no_marker'])
    print('  skipped (no LLM key)  : %d' % stats['skipped_no_llm'])
    print('  FILES CHANGED         : %d' % changed)


if __name__ == '__main__':
    main()
