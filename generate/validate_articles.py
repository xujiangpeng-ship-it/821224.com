#!/usr/bin/env python3
"""validate_articles.py — CI 硬闸门：生成后自动修复并严格校验全站文章结构。

为什么需要它（背景）：
  站点是 GitHub Actions 每天定时自动生成的，没有人工审计。generate/main.py 里
  虽然有 _repair_heading_structure 做"软修复"，但它是启发式的，遇到没见过的缺陷
  形态仍可能放行带病文章上线。本脚本是最后一道"硬闸门"：生成之后、commit 之前
  扫描全站，把已知缺陷自动修掉；若仍有修不掉的残留，直接 exit 1，使构建失败、
  不推送、不部署，从而带病页面永不发布。

修复项（与 generate/main.py 的 _repair_heading_structure 及一次性脚本保持一致，
全部零风险纯规则，只调标签不改语义）：
  1. 模板 <h1> 重复（"Title Title"）              -> 去重为单份
  2. 正文 body 内残留的 <h1>                       -> 删除（模板已渲染唯一 <h1>）
  3. h2/h3 标题副本（==文章标题）                  -> 删除
  4. 散文/多句被误标为 h2/h3                       -> 改 <p>
  5. 孤儿 h3（前面没有任何 h2）                    -> 升为 h2
  6. 超长标题（>160 字符）                          -> 改 <p>
  7. 文章缺少 Key Takeaways 区块                   -> 标记为缺陷（阻断部署，等生成器修）

用法：
  python generate/validate_articles.py            # 自动修复 + 报告
  python generate/validate_articles.py --check    # 自动修复 + 严格校验；有残留缺陷则 exit 1
  python generate/validate_articles.py --selftest # 不碰磁盘，用合成 HTML 验证修复/校验逻辑

CI 在 generate/main.py 之后、commit 之前调用 --check：
  - 修复会被后续 `git add content/` 一并提交；
  - 若仍有修不掉的缺陷，构建失败、不推送，带病页面永不部署，并触发失败邮件告警。
"""
import os
import re
import sys

# 复用 generate/ 内的既有规则，避免与生成器逻辑漂移
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fix_h2_structure import fix_body, norm, raw_text, is_multi_sentence, HEAD_RE  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'content'))
AC_OPEN = '<div class="article-content">'
CS_MARK = '<!-- COMMUNITY-SECTION-START -->'
TPL_H1 = re.compile(r'<h1>(.*?)</h1>', re.S | re.I)
ANY_H1 = re.compile(r'<h1[^>]*>.*?</h1>', re.S | re.I)
LEN_LIMIT = 160


def dedupe_title(s):
    """Collapse an accidental double title ("Title Title") to a single copy."""
    s = s.strip()
    for i, ch in enumerate(s):
        if ch == ' ':
            left, right = s[:i], s[i + 1:]
            if left == right and len(left) > 10:
                return left
    return s


def _region(text):
    """Return (ac_start, cs_end, body) for the article-content region, or (None,...) if absent."""
    ac = text.find(AC_OPEN)
    if ac == -1:
        return None, None, text
    ac += len(AC_OPEN)
    cs = text.find(CS_MARK)
    cs = len(text) if cs == -1 else cs
    return ac, cs, text[ac:cs]


def _demote_long_headings(body):
    out = []
    last = 0
    for m in HEAD_RE.finditer(body):
        out.append(body[last:m.start()])
        tag, attrs, inner = m.group(1).lower(), m.group(2), m.group(3)
        raw = raw_text(inner)
        if 'style=' in attrs.lower():
            out.append(body[m.start():m.end()])
        elif not raw.strip():
            pass  # drop empty heading (no semantic value, looks broken)
        elif len(raw) <= LEN_LIMIT:
            out.append(body[m.start():m.end()])
        else:
            out.append('<p>' + inner + '</p>')
        last = m.end()
    out.append(body[last:])
    return ''.join(out)


def fix_text(text):
    """Apply all known structural auto-fixes to one rendered article. Idempotent."""
    # 1) dedupe the template <h1> (whole-file, attribute-less)
    m = TPL_H1.search(text)
    if m:
        new = dedupe_title(m.group(1))
        if new != m.group(1):
            text = text[:m.start(1)] + new + text[m.end(1):]

    # 2) body region fixes
    ac, cs, body = _region(text)
    if ac is None:
        return text
    title_m = ANY_H1.search(text)
    title_norm = norm(title_m.group(0)) if title_m else ''

    # strip any stray <h1> the model left inside the body
    body = re.sub(r'<h1[^>]*>.*?</h1>', '', body, flags=re.S | re.I)
    # title-duplicate h2 / orphan h3 / prose->p
    body = fix_body(body, title_norm)
    # over-long headings -> p
    body = _demote_long_headings(body)

    return text[:ac] + body + text[cs:]


def residual_defects(text):
    """Return a list of still-present structural defects (empty == clean)."""
    defects = []

    # exactly one <h1> in the whole file
    h1s = ANY_H1.findall(text)
    if len(h1s) != 1:
        defects.append('h1-count=%d' % len(h1s))

    # template <h1> still doubled
    m = TPL_H1.search(text)
    if m and dedupe_title(m.group(1)) != m.group(1):
        defects.append('doubled-title')

    # missing Key Takeaways block (AdSense-relevant; generator must guarantee it)
    if 'key-takeaways' not in text.lower():
        defects.append('missing-key-takeaways')

    # body-region heading defects
    ac, cs, body = _region(text)
    if ac is not None:
        seen_h2 = False
        for mm in HEAD_RE.finditer(body):
            tag, attrs, inner = mm.group(1).lower(), mm.group(2), mm.group(3)
            raw = raw_text(inner)
            if 'style=' in attrs.lower():
                if tag == '2':
                    seen_h2 = True
                continue
            if len(raw) > LEN_LIMIT:
                defects.append('over-long-h%s(len=%d)' % (tag, len(raw)))
            elif is_multi_sentence(raw):
                defects.append('prose-h%s' % tag)
            if tag == '2':
                seen_h2 = True
            elif not seen_h2:
                defects.append('orphan-h3')

    return defects


def iter_articles():
    for dp, dn, fn in os.walk(ROOT):
        for f in fn:
            if f != 'index.html':
                continue
            rel = os.path.join(dp, f).replace('\\', '/')
            parts = rel.split('/')
            if len(parts) >= 4 and parts[-4] == 'content':
                yield rel


def main():
    if '--selftest' in sys.argv:
        return selftest()

    check = '--check' in sys.argv
    total = changed = 0
    all_defects = []
    for rel in iter_articles():
        total += 1
        text = open(rel, encoding='utf-8').read()
        fixed = fix_text(text)
        if fixed != text:
            open(rel, 'w', encoding='utf-8').write(fixed)
            changed += 1
        # re-read from disk (the saved version) and verify it is now clean
        saved = open(rel, encoding='utf-8').read()
        d = residual_defects(saved)
        if d:
            all_defects.append((rel, d))

    print("scanned: %d, auto-fixed: %d" % (total, changed))
    if check:
        if all_defects:
            print("RESIDUAL DEFECTS (build will fail — not deploying broken pages):")
            for rel, d in all_defects:
                print("  %s -> %s" % (rel, ", ".join(d)))
            print("\nACTION: inspect generate/main.py repair logic; residual defects indicate "
                  "a generator bug, not a validator gap.")
            return 1
        print("STRICT CHECK PASSED: all %d articles structurally clean." % total)
    return 0


def selftest():
    """Synthetic HTML exercising every rule; asserts fix_text + residual_defects."""
    h1x2 = (
        '<h1>My Title</h1>\n'
        '<div class="article-content">'
        '<h1>My Title</h1>'                       # stray body h1
        '<h2>My Title</h2>'                        # title-duplicate h2
        '<h2>Despite the obvious risk, the model wrote a full sentence as a heading. '
        'It should have been a paragraph instead.</h2>'   # prose h2
        '<h3>Sub point</h3>'                        # orphan h3 (no preceding h2)
        '<h2>This heading is far too long to be a real section label and clearly '
        'represents an entire paragraph of prose that the model mistakenly wrapped '
        'in a heading tag which is exactly the kind of defect we must never ship.</h2>'
        '<section class="key-takeaways"><h2 style="margin-top:2rem">Key Takeaways</h2>'
        '<ul><li>one</li></ul></section>'
        '</div>'
    )
    fixed = fix_text(h1x2)
    d = residual_defects(fixed)
    assert '<h1>My Title</h1>\n<div' in fixed, "stray body h1 not stripped"
    assert fixed.count('<h1') == 1, "more than one h1 remains"
    assert '<h2>My Title</h2>' not in fixed, "title-duplicate h2 not removed"
    assert fixed.count('<p>') >= 2, "prose/long headings not demoted to <p>"
    assert '<h3>Sub point</h3>' not in fixed, "orphan h3 not promoted"
    assert d == [], "residual defects after fix: %r" % d

    # doubled template title
    doubled = ('<h1>Big Long Title Big Long Title</h1>'
               '<div class="article-content"><h2>Real</h2>'
               '<section class="key-takeaways"></section></div>')
    fd = fix_text(doubled)
    assert '<h1>Big Long Title</h1>' in fd, "doubled title not deduped: %r" % fd
    assert residual_defects(fd) == [], "doubled-title residual"

    # clean input should be untouched
    clean = ('<h1>Ok</h1><div class="article-content"><h2>Intro</h2><p>x</p>'
             '<section class="key-takeaways"></section></div>')
    assert fix_text(clean) == clean, "clean input was modified"
    assert residual_defects(clean) == [], "clean input flagged"

    # styled Key Takeaways / Comments headings must survive untouched
    styled = ('<h1>T</h1><div class="article-content">'
              '<h2 style="margin-top:2rem">Key Takeaways</h2>'
              '<p>point</p>'
              '<h2 style="margin-top:2rem">Community Perspectives</h2>'
              '</div>')
    fs = fix_text(styled)
    assert 'style="margin-top:2rem"' in fs, "styled heading was altered"
    assert 'key-takeaways' not in fs.lower(), "selftest fixture lacks KT marker by design"

    print("SELFTEST PASSED: all 7 rules verified (h1 dedupe, body-h1 strip, "
          "title-dup h2, prose->p, orphan h3, over-long->p, styled-survival).")
    return 0


if __name__ == '__main__':
    sys.exit(main())
