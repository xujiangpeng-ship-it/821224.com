"""
Comprehensive remediation for legacy 821224.com articles.

For every article page under content/<subdomain>/<slug>/index.html:
  - if it already matches the COMPLETE benchmark template  -> skip
  - else if its body contains unambiguous LLM chat leakage -> regenerate a clean
    body via the LLM, then render with the benchmark template
  - else (legacy/hybrid template, clean body)              -> extract existing body
    and re-render with the benchmark template

Run with Python that has yaml + jinja2 + mistralai, and MISTRAL_API_KEY + proxy set.
"""
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = ROOT / "content"
TEMPLATES_DIR = ROOT / "templates"

sys.path.insert(0, str(ROOT))
from llm import generate_text
import quality_enhancement as qe
import re_render_articles as rr

# Unambiguous LLM chat-leakage markers (definitely not real article prose).
STRONG_LEAK = [
    "Here's a forward-looking", "Here is the enhanced", "Here's the enhanced article",
    "rewrite of your paragraph", "Key adjustments/notes", "Key adjustments:",
    "I'll rewrite", "As an AI language model", "As an AI, I", "Certainly!", "Sure!",
    "Absolutely!", "Let me tell you something they won't", "Here's a rewritten",
    "I've rewritten", "Below is a rewritten", "Here's a cleaner", "I've drafted",
    "rewrite of the paragraph", "Here is a rewritten version",
]

PERSPECTIVE = {
    "ai-claims": "Claims Adjuster / FNOL Specialist with 12+ years in claims operations",
    "ai-underwriting": "CTO / VP of Engineering who has shipped underwriting models to production",
    "ai-fraud-detection": "Data Science Lead running fraud detection models at a carrier",
    "embedded-insurance": "Product Manager at an MGA launching embedded insurance products",
    "ai-policy-cx": "Product Manager owning policyholder digital experience",
    "decision-intelligence": "Chief Data Officer driving insurance AI strategy",
}


def has_strong_leak(html: str) -> bool:
    return any(mk in html for mk in STRONG_LEAK)


def clean_generated_body(text: str) -> str:
    """Strip code fences and any chatbot preamble before the first real HTML tag."""
    if not text:
        return ""
    text = text.strip()
    for pat in [r'```html\s*\n(.*?)```', r'```\s*\n(.*?)```']:
        m = re.search(pat, text, re.DOTALL)
        if m:
            text = m.group(1).strip()
            break
    start = re.search(r'<(h[1-6]|p|table|ul|ol|div|blockquote|figure|pre|section|article)\b', text, re.IGNORECASE)
    if start:
        text = text[start.start():]
    return rr.fix_html_body(text.strip())


def render(html_body, title, description, keyword, subdomain, subdomain_name,
           url, date_display, date_iso, faq_schema, howto_schema, now):
    content_first, content_rest = rr.split_content_at_third(html_body)
    adsense = rr.load_config().get("adsense", {})
    pub_id = adsense.get("pub_id", "")
    ad_slots = adsense.get("ad_units", {})
    date_modified_iso = date_iso
    return Environment(loader=FileSystemLoader(str(TEMPLATES_DIR))).get_template("article.html").render(
        site_name=rr.load_config()["site"]["name"],
        subdomains=rr.load_config()["subdomains"],
        current_year=now.year,
        current_date=date_display or now.strftime("%B %d, %Y"),
        title=title, description=description, keyword=keyword,
        content=html_body, content_first=content_first, content_rest=content_rest,
        date_iso=date_iso, date_modified_iso=date_modified_iso, date_display=date_display,
        subdomain=subdomain, subdomain_name=subdomain_name,
        adsense_pub_id=pub_id or None,
        ad_slot_top=ad_slots.get("top_banner", {}).get("slot", ""),
        ad_slot_in=ad_slots.get("in_content", {}).get("slot", ""),
        ad_slot_bottom=ad_slots.get("bottom", {}).get("slot", ""),
        canonical_url=url,
        ga_id=rr.load_config().get("analytics", {}).get("ga_id", ""),
        faq_schema=faq_schema or None, howto_schema=howto_schema or None,
    )


def main():
    config = rr.load_config()
    sd_names = {sd["slug"]: sd["name"] for sd in config["subdomains"]}
    now = datetime.now(timezone.utc)

    index_path = CONTENT_DIR / "index.json"
    index_lookup = {}
    if index_path.exists():
        for e in json.loads(index_path.read_text(encoding="utf-8")):
            index_lookup[e.get("url", "")] = e

    regenerated = retemplated = skipped = failed = 0

    for sf in sorted(CONTENT_DIR.iterdir()):
        if not sf.is_dir():
            continue
        subdomain = sf.name
        subdomain_name = sd_names.get(subdomain, subdomain.replace("-", " ").title())
        for af in sorted(sf.iterdir()):
            if not af.is_dir():
                continue
            article_file = af / "index.html"
            if not article_file.exists():
                continue
            slug = af.name
            url = f"/{subdomain}/{slug}/"
            old_html = article_file.read_text(encoding="utf-8")

            if rr.is_benchmark_clean(old_html):
                skipped += 1
                continue

            meta = index_lookup.get(url, {})
            title = meta.get("title") or rr.extract_title(old_html)
            description = meta.get("description") or rr.extract_description(old_html)
            date_display = meta.get("date_display", "")
            keyword = meta.get("keyword", slug.replace("-", " "))
            date_iso = ""
            if date_display:
                try:
                    date_iso = datetime.strptime(date_display, "%B %d, %Y").strftime("%Y-%m-%dT%H:%M:%S+00:00")
                except ValueError:
                    date_iso = ""

            body = None
            if has_strong_leak(old_html):
                perspective = PERSPECTIVE.get(subdomain, "senior insurance technology analyst")
                user = (
                    f"Write the complete article body (HTML) for this assignment.\n\n"
                    f"Title: {title}\nSubdomain: {subdomain_name}\n"
                    f"Primary keyword: {keyword}\nPerspective: {perspective}\n\n"
                    f"Requirements: 2000+ words; cite real organizations + year + report names "
                    f"(at least 3); include at least one 4x4 comparison table; reference related "
                    f"articles under /{subdomain}/ naturally; sentence-case headings; NO em/en dashes; "
                    f"never say 'As an AI'. Output ONLY raw HTML body (<h2>,<h3>,<p>,<ul>,<li>,<table>) "
                    f"— no preamble, no code fences."
                )
                try:
                    gen = generate_text(qe.ENHANCED_SYSTEM_PROMPT, user, temperature=0.7, max_tokens=5000)
                    body = clean_generated_body(gen)
                except Exception as e:
                    print(f"  LLM FAIL {url}: {e}")
                    failed += 1
                if body:
                    regenerated += 1
                else:
                    # Fallback: keep existing (structure will still be fixed below)
                    body = rr.extract_article_body(old_html)
            else:
                body = rr.extract_article_body(old_html)
                retemplated += 1

            if not body:
                print(f"  SKIP(no body) {url}")
                skipped += 1
                continue

            faq = rr.extract_faq_schema(body)
            howto = rr.extract_howto_schema(body, title, description)
            html = render(body, title, description, keyword, subdomain, subdomain_name,
                         url, date_display, date_iso, faq, howto, now)
            article_file.write_text(html, encoding="utf-8")
            print(f"  {'REGEN' if (has_strong_leak(old_html) and body) else 'RETEMPLATE'} {url} -> {str(title)[:55]}")

    print(f"\nDone: regenerated={regenerated}, retemplated={retemplated}, "
          f"llm_failed={failed}, skipped={skipped}.")


if __name__ == "__main__":
    main()
