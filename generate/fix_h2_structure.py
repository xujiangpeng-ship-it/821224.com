#!/usr/bin/env python3
"""fix_h2_structure.py — 修复 821224 全站 h2/h3 结构错位 (bug class: 长标题误用H2 + 降级真标题)

规则（全部零风险纯规则，不改语义内容，只调标签）：
  1. 删除 text == 文章标题(h1) 的 <h2>（标题副本，68篇）-> 直接去掉该标签。
  2. 多句段落被误标为 <h2> 的（含句末标点+大写，或 run-on）-> 改 <p>。
  3. 经 1/2 处理后，正文里“前面没有任何 h2”的孤儿 <h3>（即被降级的一级分节）
     -> 升为 <h2>。自然语言生成的 body 标题一律无 style 属性；带 style= 的
     （Key Takeaways / Comments）原样保留。

用法：
  python fix_h2_structure.py --dry      # 只统计，不写文件
  python fix_h2_structure.py           # 实际改写 content/**/index.html
"""
import os, re, html, sys

ROOT = os.path.join(os.path.dirname(__file__), '..', 'content')
ROOT = os.path.abspath(ROOT)

SKIP_MARKERS = ('key takeaways', 'community perspectives', 'comments')

def norm(s):
    s = re.sub(r'<[^>]+>', '', s)
    s = html.unescape(s).strip().lower()
    s = re.sub(r'[^a-z0-9 ]', '', s)
    return re.sub(r'\s+', ' ', s).strip()

def raw_text(inner):
    return re.sub(r'<[^>]+>', '', inner).strip()

def is_multi_sentence(s):
    # 句末标点(./!/?)后跟 空格+大写 = 多句散文
    if re.search(r'[.?!]\s+[A-Z]', s):
        return True
    # 标题内含换行（LLM 把整段散文塞进 <h*>）= 散文
    if '\n' in s:
        return True
    if '.” ' in s or '." ' in s or '?” ' in s:
        return True
    return False

HEAD_RE = re.compile(r'<h([23])([^>]*)>(.*?)</h\1>', re.S | re.I)

def fix_body(body, title_norm):
    """统一修复逻辑（幂等）：
      - 多句散文被误标为任何标题(h2/h3) -> 改 <p>（保留文本，仅调标签）
      - 真实标题：
          * h2 且 == 文章标题 -> 删除（标题副本）
          * h2 真实 -> 保留
          * h3 且前面没有任何 h2（孤儿一级分节）-> 升 h2
          * h3 嵌套在 h2 下 -> 保留
      带 style= 的（Key Takeaways / Comments）原样保留。
    """
    out = []
    last = 0
    seen_h2 = False
    for m in HEAD_RE.finditer(body):
        out.append(body[last:m.start()])
        tag = m.group(1).lower()
        attrs = m.group(2)
        inner = m.group(3)
        raw = raw_text(inner)
        nrm = norm(raw)
        if 'style=' in attrs.lower():
            out.append(body[m.start():m.end()])   # KT/Comments 保留
            if tag == '2':
                seen_h2 = True
            last = m.end()
            continue
        if tag == '2' and title_norm and nrm == title_norm:
            last = m.end()                          # 标题副本 -> 删除
            continue
        if is_multi_sentence(raw):
            out.append('<p>' + inner + '</p>')      # 散文误标 -> 段落
            last = m.end()
            continue
        if tag == '2':
            out.append(body[m.start():m.end()])      # 真实 h2 保留
            seen_h2 = True
        else:  # h3
            if not seen_h2:
                out.append('<h2' + attrs + '>' + inner + '</h2>')  # 降级 -> 升 h2
            else:
                out.append(body[m.start():m.end()])                # 真实 h3 保留
        last = m.end()
    out.append(body[last:])
    return ''.join(out)

def process(rel, dry):
    t = open(rel, encoding='utf-8').read()
    m = re.search(r'<h1[^>]*>(.*?)</h1>', t, re.S | re.I)
    title_norm = norm(m.group(1)) if m else ''
    ac_tag = '<div class="article-content">'
    ac_open = t.find(ac_tag)
    if ac_open == -1:
        return None
    ac_open += len(ac_tag)
    cs_idx = t.find('<!-- COMMUNITY-SECTION-START -->')
    if cs_idx == -1:
        cs_idx = len(t)
    body = t[ac_open:cs_idx]
    new_body = fix_body(body, title_norm)
    if new_body == body:
        return None
    # 统计变化
    before = HEAD_RE.findall(body)
    after = HEAD_RE.findall(new_body)
    cnt = {'h2_del': 0, 'h2_to_p': 0, 'h3_to_h2': 0}
    # 粗略：对比标签数变化
    # 用更精确的方式：重新跑 fix_body 的计数版本
    stat = count_changes(body, title_norm)
    if not dry:
        nt = t[:ac_open] + new_body + t[cs_idx:]
        open(rel, 'w', encoding='utf-8').write(nt)
    return stat

def count_changes(body, title_norm):
    seen_h2 = False
    c = {'h2_del': 0, 'prose_to_p': 0, 'h3_to_h2': 0}
    for m in HEAD_RE.finditer(body):
        tag = m.group(1).lower(); attrs = m.group(2); inner = m.group(3)
        raw = raw_text(inner); nrm = norm(raw)
        if 'style=' in attrs.lower():
            if tag == '2': seen_h2 = True
            continue
        if tag == '2' and title_norm and nrm == title_norm:
            c['h2_del'] += 1; continue
        if is_multi_sentence(raw):
            c['prose_to_p'] += 1
            continue
        if tag == '2':
            seen_h2 = True
        else:
            if not seen_h2:
                c['h3_to_h2'] += 1
    return c

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
    tot = {'h2_del': 0, 'prose_to_p': 0, 'h3_to_h2': 0}
    changed = 0
    for rel in files:
        r = process(rel, dry)
        if r:
            changed += 1
            for k in tot: tot[k] += r[k]
    print(f"{'[DRY-RUN] ' if dry else ''}files scanned: {len(files)}, changed: {changed}")
    print(f"  h2 title-duplicate removed : {tot['h2_del']}")
    print(f"  prose heading -> <p>       : {tot['prose_to_p']}")
    print(f"  h3 demoted -> <h2>         : {tot['h3_to_h2']}")

if __name__ == '__main__':
    main()
