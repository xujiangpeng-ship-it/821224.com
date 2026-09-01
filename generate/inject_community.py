# -*- coding: utf-8 -*-
"""
inject_community.py — 把「社区视角」区块回填进已发布的文章

适用场景
--------
模板与生成管线已接好（main.py render_article 会自动注入），
但之前已渲染的 199 篇文章 HTML 里还没有这个区块。本脚本给它们补上。

半自动：只对 COMMUNITY_THEMES 里的主题（默认 ai_claims / ai_fraud）回填。
每篇结果按 (theme, slug) 缓存到 .community_cache/，重复运行复用、不重复花额度。

用法
----
    # 需要社区内容时（会调 Reddit/HN）：
    COMMUNITY_ENABLE=1 SCRAPECREATORS_API_KEY=xxxx python inject_community.py
    # 仅看会处理哪些文章、不调 API：
    python inject_community.py --dry

注意
----
- 必须设 COMMUNITY_ENABLE=1 才会真正抓取；否则所有篇的区块都返回 ""，脚本只报告
  “待注入”而不改文件，避免自动 cron 误跑时乱花 ScrapeCreators 额度。
- Reddit 经 ScrapeCreators：每篇约 1（search）+ 最多 2（评论）= 3 credit。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = ROOT / "content"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import community_sources as cs  # noqa: E402
import community_sources_config as cfg  # noqa: E402

START = "<!-- COMMUNITY-SECTION-START -->"
END = "<!-- COMMUNITY-SECTION-END -->"


def _subdomains_for_themes() -> dict:
    """theme -> 子目录名（反向查 SUBDOMAIN_TO_THEME）。"""
    out = {}
    for sub, theme in cfg.SUBDOMAIN_TO_THEME.items():
        if theme in cfg.COMMUNITY_THEMES:
            out[sub] = theme
    return out


def _extract_title(html: str) -> str:
    m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    if m:
        t = m.group(1).split(" | ")[0].strip()
        return t
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
    if m:
        return re.sub(r"<[^>]+>", "", m.group(1)).strip()
    return ""


def _keyword_for(subdomain: str, slug: str) -> str:
    """尽量从 index.json 取该篇 keyword；没有则用空（build 会回退 title）。"""
    idx = CONTENT_DIR / "index.json"
    if idx.exists():
        try:
            for e in json.loads(idx.read_text(encoding="utf-8")):
                if e.get("url", "").strip("/") == f"{subdomain}/{slug}":
                    return e.get("keyword", "") or ""
        except Exception:
            pass
    return ""


def _inject_into_article_content(html: str, fragment: str) -> tuple[str, bool]:
    """无锚点文章：把 fragment 插到最外层 <div class="article-content"> 闭合之后。

    用 div 开闭计数定位 article-content 自身的闭合标签，避免误伤内部 ad-slot 等嵌套 div。
    """
    start = html.find('<div class="article-content">')
    if start == -1:
        return html, False
    pos = html.find(">", start) + 1
    depth = 1
    while pos < len(html):
        nxt_open = html.find("<div", pos)
        nxt_close = html.find("</div>", pos)
        if nxt_close == -1:
            break
        if nxt_open != -1 and nxt_open < nxt_close:
            depth += 1
            pos = nxt_open + 4
        else:
            depth -= 1
            close_end = nxt_close + len("</div>")
            pos = close_end
            if depth == 0:
                return html[:close_end] + "\n" + fragment + "\n" + html[close_end:], True
    return html, False


def inject_one(subdomain: str, slug: str, html: str) -> tuple[str, str]:
    """返回 (status, new_html)。status: skip | injected | empty"""
    title = _extract_title(html)
    keyword = _keyword_for(subdomain, slug)
    section = cs.build_community_section(subdomain, title, slug, keyword)
    if not section:
        return "empty", html
    # 情况 A：已有锚点且为空 -> 填进去
    if START in html and END in html:
        block = html[html.index(START) + len(START):html.index(END)]
        if block.strip():
            return "skip", html  # 已注入过
        new_html = html[:html.index(START) + len(START)] + section + html[html.index(END):]
        return "injected", new_html
    # 情况 B：旧模板渲染的文章（无锚点）-> 插到 article-content 闭合后
    new_html, ok = _inject_into_article_content(html, START + section + END)
    if ok:
        return "injected", new_html
    return "skip", html


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="只报告待处理文章，不调 API、不改文件")
    args = ap.parse_args()

    enabled = os.environ.get(cfg.COMMUNITY_ENABLE_ENV) == "1"
    print(f"[config] COMMUNITY_ENABLE={'1 (抓取开启)' if enabled else 'unset (dry-only)'}")
    print(f"[config] themes={cfg.COMMUNITY_THEMES} subdomains={_subdomains_for_themes()}")

    if args.dry:
        enabled = False  # dry 强制不调 API

    stats = {"injected": 0, "empty": 0, "skip": 0, "pending": 0}
    for subdomain, theme in _subdomains_for_themes().items():
        sd = CONTENT_DIR / subdomain
        if not sd.is_dir():
            continue
        for af in sorted(sd.iterdir()):
            if not af.is_dir() or not (af / "index.html").exists():
                continue
            slug = af.name
            html = (af / "index.html").read_text(encoding="utf-8")
            if START in html:
                block = html[html.index(START) + len(START):html.index(END)]
                if block.strip():
                    stats["skip"] += 1  # 已注入
                    continue
            # 无锚点（旧模板渲染）或锚点为空 -> 待回填
            stats["pending"] += 1
            if args.dry or not enabled:
                continue
            status, new_html = inject_one(subdomain, slug, html)
            if status == "injected":
                (af / "index.html").write_text(new_html, encoding="utf-8")
                stats["injected"] += 1
                print(f"  injected  {subdomain}/{slug}")
            elif status == "empty":
                stats["empty"] += 1
                print(f"  empty     {subdomain}/{slug} (no relevant community content)")
            # 限速：每篇之间停顿，避免批量回填触发 ScrapeCreators 速率限制（429）。
            # 即使撞墙，build_community_section 的缓存会保留已成功的篇，重跑只补缺失。
            time.sleep(4)
    print(f"\n[done] pending={stats['pending']} injected={stats['injected']} "
          f"empty={stats['empty']} already_or_old={stats['skip']}")


if __name__ == "__main__":
    main()
