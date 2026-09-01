"""
Insurtech Insights — Content Generation Pipeline
Usage: python generate/main.py [--count N]
"""

import argparse
import json
import logging
import os
import random
import re
import sys
import textwrap
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape as escape_xml

import yaml
from jinja2 import Environment, FileSystemLoader

from llm import generate_text
from pipeline.deai import deai_process
from pipeline.generator_v2 import enhance_article

# Community-perspectives block (真人讨论策展，提升 E-E-A-T)。
# build_community_section 默认不调 API（需 COMMUNITY_ENABLE=1 + 主题在允许列表），
# 失败/未启用时返回 "" —— 绝不阻断文章生成。
try:
    from community_sources import build_community_section
except Exception:  # 模块缺失不致命
    build_community_section = None

# PIL for image dimension retrieval (WebP width/height injection)
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("main")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
CONTENT_DIR = ROOT / "content"
# ---------------------------------------------------------------------------
# Chat Widget Injection
# ---------------------------------------------------------------------------
_WIDGET_SCRIPT = (
    '<script>window.ChatWidgetConfig={apiBase:"https://insurtech-cs-worker.wicro.workers.dev",shopId:"821224",title:"Assistant"}</script>'
    '<script src="https://insurtech-cs-worker.wicro.workers.dev/chat-widget.js" defer></script>'
)

def inject_widget(html_path):
    """Inject chat widget script before </body> tag."""
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            html = f.read()
        if 'ChatWidgetConfig' not in html and '</body>' in html:
            html = html.replace('</body>', _WIDGET_SCRIPT + '\n</body>')
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html)
        logger.info('Injected widget into %s', html_path)
    except Exception as e:
        logger.warning('Failed to inject widget into %s: %s', html_path, e)



CATEGORY_HERO = {
    "ai-claims": {
        "badge": "Claims Automation",
        "heading": "AI Claims<br>Intelligence",
        "subtitle": "From FNOL to settlement, machine learning rewrites the claims playbook. Explore practical implementations of automated triage, damage estimation, fraud screening, and subrogation — covering both established carriers and insurtech challengers. Each article goes beyond vendor claims to examine ROI frameworks, implementation timelines, and common failure modes."
    },
    "ai-underwriting": {
        "badge": "Underwriting Innovation",
        "heading": "AI Underwriting<br>Insights",
        "subtitle": "Risk assessment at machine speed. This category covers automated underwriting engines powered by structured and unstructured data — from telematics and IoT feeds to NLP-enriched broker submissions. Deep dives into loss ratio impact, regulatory friction, and the shift from 'detect and reject' to 'price and accept.'"
    },
    "ai-fraud-detection": {
        "badge": "Fraud Prevention",
        "heading": "AI Fraud Detection<br>Deep Dives",
        "subtitle": "Catching what rule-based systems miss. Technical analysis of deep learning, graph neural networks, and NLP applied to claims fraud — covering application fraud, organized rings, provider fraud, and premium leakage. Includes model development guides, dataset strategies, and the thorny problem of explainability."
    },
    "embedded-insurance": {
        "badge": "Embedded Insurance",
        "heading": "Embedded Insurance<br>Frontier",
        "subtitle": "Insurance seamlessly embedded into checkout flows, ride-hailing apps, and SaaS platforms. Coverage spans API-first architectures, regulatory fragmentation across jurisdictions, risk pooling mechanics, and the economic fundamentals that will determine which embedded models survive consolidation."
    },
    "ai-policy-cx": {
        "badge": "Policy & CX",
        "heading": "AI-Powered Policy<br>& Customer Experience",
        "subtitle": "Chatbots, hyper-personalization, and proactive retention — AI is redefining how carriers interact with policyholders. Articles cover conversational AI deployment patterns, churn prediction models, omnichannel orchestration, and the metrics that matter: NPS, retention rate, and lifetime value."
    }
}

CATEGORY_META_DESCRIPTIONS = {
    "ai-claims": "AI-driven claims processing strategies that cut cycle times by 40-60% and reduce leakage. Practical guides on FNOL triage, damage estimation, fraud screening, settlement automation, and ROI frameworks — all backed by real-world insurance implementations at 821224.com.",
    "ai-underwriting": "Deep dives into AI underwriting engines using IoT telematics, NLP, and predictive modeling to slash quote cycle time by 99%. Covers automated risk assessment, loss ratio optimization, regulatory compliance, and the shift to 'price and accept' strategies.",
    "ai-fraud-detection": "Technical analysis of deep learning, graph neural networks, and anomaly detection for insurance fraud prevention. Model development guides, dataset strategy, and explainability — targeting the $40B+ annual fraud leakage problem in global insurance.",
    "embedded-insurance": "API-first embedded insurance architectures reshaping distribution across checkout flows, ride-hailing, and SaaS platforms. Regulatory fragmentation analysis, risk pooling mechanics, and market projections for the $700B embedded opportunity by 2030.",
    "ai-policy-cx": "Conversational AI, hyper-personalization, and churn prediction for insurance customer experience. Implementation guides covering chatbots, omnichannel orchestration, NPS optimization, and proactive retention strategies for carriers.",
    "decision-intelligence": "Insurance AI maturity models, data strategy frameworks, and organizational transformation guides. Build-vs-buy talent decisions, governance, ROI measurement — moving carriers from PoC purgatory to production-grade AI.",
}
KEYWORDS_DIR = ROOT / "keywords"
TEMPLATES_DIR = ROOT / "templates"

DEFAULT_IMG_W = 800
DEFAULT_IMG_H = 450



def inject_csp(html_path):
    """Inject CSP meta tag to override header CSP for widget scripts."""
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            html = f.read()
        csp_value = (
            "script-src 'self' 'unsafe-inline' "
            "https://www.googletagmanager.com "
            "https://pagead2.googlesyndication.com "
            "https://static.cloudflareinsights.com "
            "https://insurtech-cs-worker.wicro.workers.dev; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https://pagead2.googlesyndication.com; "
            "connect-src 'self' https://www.google-analytics.com "
            "https://api.github.com "
            "https://pagead2.googlesyndication.com "
            "https://www.googletagmanager.com "
            "https://insurtech-cs-worker.wicro.workers.dev; "
            "frame-src https://pagead2.googlesyndication.com "
            "https://insurtech-cs-worker.wicro.workers.dev;"
        )
        csp_meta = f'<meta http-equiv="Content-Security-Policy" content="{csp_value}">'
        if 'Content-Security-Policy' not in html and '</head>' in html:
            html = html.replace('</head>', csp_meta + '\n</head>')
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html)
            logger.info('Injected CSP meta tag into %s', html_path)
    except Exception as e:
        logger.warning('Failed to inject CSP into %s: %s', html_path, e)


def get_image_dimensions(src: str) -> tuple:
    """Resolve img src to local file, return (width, height) or defaults."""
    if not HAS_PIL:
        return DEFAULT_IMG_W, DEFAULT_IMG_H
    if src.startswith("/"):
        img_path = CONTENT_DIR / src.lstrip("/")
    elif src.startswith("http"):
        return DEFAULT_IMG_W, DEFAULT_IMG_H
    else:
        img_path = CONTENT_DIR / src
    try:
        if img_path.exists():
            with Image.open(str(img_path)) as img:
                return img.size
    except Exception:
        pass
    return DEFAULT_IMG_W, DEFAULT_IMG_H


def load_config():
    with open(ROOT / "config.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------------------
# Keyword Picker
# ---------------------------------------------------------------------------

def pick_unused_keywords(config, count: int):
    """Pick *count* unused keywords using load-balanced subdomain selection.
    
    Prioritizes subdomains with the fewest published articles to ensure even
    content distribution across all categories.
    """
    subdomains = config["subdomains"]

    # Count existing articles per subdomain
    sd_counts = {}
    for sd in subdomains:
        sd_dir = CONTENT_DIR / sd["slug"]
        if sd_dir.is_dir():
            sd_counts[sd["slug"]] = sum(1 for d in sd_dir.iterdir() if d.is_dir())
        else:
            sd_counts[sd["slug"]] = 0

    # Load available (unused) keywords per subdomain
    sd_keywords = {}
    for sd in subdomains:
        kw_path = KEYWORDS_DIR / f"{sd['slug']}.json"
        if not kw_path.exists():
            logger.warning("Keyword file not found: %s", kw_path)
            continue
        with open(kw_path, encoding="utf-8") as fh:
            keywords = json.load(fh)
        available = [kw for kw in keywords if not kw.get("is_used", False)]
        if available:
            sd_keywords[sd["slug"]] = available

    if not sd_keywords:
        logger.error("No unused keywords available in any subdomain.")
        return []

    # Sort subdomains by article count ascending (fewest first)
    sorted_sds = sorted(sd_counts.items(), key=lambda x: x[1])
    selected = []
    for sd_slug, _ in sorted_sds:
        if len(selected) >= count:
            break
        if sd_slug in sd_keywords and sd_keywords[sd_slug]:
            kw = random.choice(sd_keywords[sd_slug])
            selected.append(kw)
            sd_keywords[sd_slug].remove(kw)  # prevent double-pick within same run

    if len(selected) < count:
        logger.warning(
            "Only %d keywords available across all subdomains (requested %d).",
            len(selected), count
        )

    return selected


def mark_pending(keyword_entry):
    """Set is_used=True with pending marker — called BEFORE generation to
    prevent concurrent runs from picking the same keyword."""
    subdomain = keyword_entry["subdomain"]
    kw_path = KEYWORDS_DIR / f"{subdomain}.json"
    with open(kw_path, encoding="utf-8") as fh:
        keywords = json.load(fh)
    for kw in keywords:
        if kw["keyword"] == keyword_entry["keyword"]:
            kw["is_used"] = True
            kw["generated_at"] = "pending"
            break
    with open(kw_path, "w", encoding="utf-8") as fh:
        json.dump(keywords, fh, indent=2, ensure_ascii=False)


def mark_completed(keyword_entry):
    """Update generated_at to real timestamp — called AFTER successful render."""
    subdomain = keyword_entry["subdomain"]
    kw_path = KEYWORDS_DIR / f"{subdomain}.json"
    with open(kw_path, encoding="utf-8") as fh:
        keywords = json.load(fh)
    for kw in keywords:
        if kw["keyword"] == keyword_entry["keyword"]:
            kw["generated_at"] = datetime.now(timezone.utc).isoformat()
            break
    with open(kw_path, "w", encoding="utf-8") as fh:
        json.dump(keywords, fh, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Content Generation
# ---------------------------------------------------------------------------

def _clean_llm_body_response(text: str) -> str:
    """Strip ```html fences and chatbot preamble from LLM body-content responses.

    Unlike _clean_llm_html_response (which expects full HTML with DOCTYPE),
    this handles the Pass 1 output which should be bare HTML body content
    (h2, p, table, ul, etc. — no DOCTYPE / html / head / body tags).
    """
    if not text or not text.strip():
        return text

    # Step 1: Extract content from ```html / ``` code fences
    fence_patterns = [
        r'```html\s*\n(.*?)```',
        r'```\s*\n(.*?)```',
    ]
    for pattern in fence_patterns:
        m = re.search(pattern, text, re.DOTALL)
        if m:
            text = m.group(1).strip()
            break

    # Step 2: Find where real HTML body content begins
    # Body content starts with <h2>, <h3>, <p>, <table>, <ul>, <ol>, etc.
    body_start_patterns = [
        r'<(h[1-6]|p|table|ul|ol|div|blockquote|figure|pre|section|article)\b',
    ]
    for pattern in body_start_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            text = text[m.start():]
            break

    return text.strip()


CONTENT_LENGTH_RULES = {
    "tutorial":       (2000, 4000),
    "tool-review":    (1200, 2000),
    "news":           (1200, 1800),
    "comparison":     (1500, 2500),
    "explainer":      (1500, 3000),
    "case-study":     (1200, 2500),
    "how-to":         (1200, 2500),
}

SYSTEM_PROMPT = textwrap.dedent("""\
You are a senior insurance technology analyst writing for "Insurtech Insights" — a Gartner/Forrester-caliber publication covering AI in insurance. Your tone: confident, direct, data-driven, skeptical where warranted.

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  DE-AI WRITING CONSTRAINTS — VIOLATE THESE AND THE ARTICLE   ┃
┃  WILL BE REJECTED BY HUMAN READERS AND DETECTION TOOLS.      ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

═══════════════════════════════════════════════════════════════
SECTION 1: FORBIDDEN VOCABULARY — DELETE ON SIGHT
═══════════════════════════════════════════════════════════════

BLACKLIST WORDS (TIER 1 — instant rejection if found):
  crucial, pivotal, vital, delve, showcase, tapestry, landscape (abstract),
  vibrant, testament, underscore, fosters, interplay, intricate, nestled,
  breathtaking, groundbreaking, in the heart of, renowned, must-visit,
  commitment to excellence, game-changer, game changing, revolutionary,
  cutting-edge, paradigm shift, unlock the power of, harness the power of,
  garner, enduring, cultivating, encompassing

BLACKLIST WORDS (TIER 2 — replace with simpler alternatives):
  • serves as / stands as / marks / represents / boasts → use "is" / "are" / "has"
  • additionally → "also" or delete
  • enhance → "improve"
  • showcase (verb) → "show"
  • Moreover / Furthermore → "Beyond that" / "What's more" (sparingly)
  • Therefore / Thus → "So" / "Which means"
  • However → "But" / "That said"
  • Consequently / As a result → "So what happened was"

═══════════════════════════════════════════════════════════════
SECTION 2: FORBIDDEN SYNTACTIC PATTERNS
═══════════════════════════════════════════════════════════════

2.1 PUNCTUATION — HARD BANS
  • EM DASH (—) and EN DASH (-): NEVER use. Replace with period (new sentence),
    comma, or colon. These are the single most reliable AI markers.
  • Curly quotes (""): use straight quotes ("") only.
  • EMOJI: absolutely forbidden in any form.

2.2 FORBIDDEN SENTENCE STRUCTURES
  • "Not only... but also..." → Just state the point directly.
  • "It's not just about X, it's about Y" → State Y directly.
  • "From X to Y" (false scope) → List items plainly.
  • "X is the Y of Z" (aphorism formulas) → Say what you actually mean.
  • "The real question is..." / "At its core..." / "What really matters..." →
    Just state the point without the authority-preface.

2.3 FORBIDDEN -ING PADDING CLAUSES
  Never end a sentence with a comma followed by:
    highlighting, underscoring, emphasizing, ensuring, reflecting,
    symbolizing, contributing to, cultivating, fostering, encompassing,
    showcasing
  → Break into two sentences instead.

2.4 FORBIDDEN ROAD SIGNS (delete these entirely — start the content directly):
  • "Let's dive in" / "Let's explore" / "Let's break this down"
  • "Here's what you need to know" / "Without further ado"
  • "I hope this helps" / "Let me know if..." / "Would you like me to..."
  • "Certainly!" / "Of course!" / "Great question!"
  • "In conclusion" / "To sum up" / "In summary" / "Ultimately"

2.5 FORBIDDEN STRUCTURAL TEMPLATES
  • Three-item syndrome: avoid dense repetitions of "A, B, and C". Vary your
    list lengths — sometimes 2 items, sometimes 4, or no list at all.
  • "Despite its challenges, X continues to thrive" template → Replace with
    specific problems and specific actions.
  • "The future looks bright" / "Exciting times lie ahead" / "X represents
    a major step forward" → Delete. End with a specific observation or question.
  • Fragment title syndrome: after an <h2>, never write a sentence that just
    rephrases the heading. Jump straight into content.

2.6 FORBIDDEN ATTRIBUTION PATTERNS
  • "Experts believe" / "Observers have cited" / "Some critics argue" →
    Name the specific source or delete the claim.
  • "Studies show" / "Research indicates" / "Industry data suggests" →
    Name institution + year + report title, or make no claim.
  • "Based on available information" / "While details are limited" /
    "It is believed that" → If you don't know, say so. Don't pad.

2.7 FORBIDDEN STYLE HABITS
  • Adjective stacking: one per noun, two max only when both are precise.
  • Elegant variation: don't use 3+ different terms for the same entity
    across adjacent sentences. Pick the clearest term and repeat it.
  • All headings MUST use sentence case (only first word and proper nouns
    capitalized). NEVER use Title Case.
  • Do not systematically bold technical terms. Use italics sparingly
    (max 3 per article) for genuine emphasis.
  • Avoid inline bold-keyword lists ("- **Term:** definition") —
    rewrite as natural paragraphs.
  • No manufactured quotables: don't write 3+ consecutive ultra-short
    sentences to create dramatic effect.
  • No conversational openings: "Honestly?" / "Look," / "Here's the thing,"
  • No hyphenated word-pair overuse: third-party, cross-functional,
    data-driven, real-time — use only as adjectives before nouns.

═══════════════════════════════════════════════════════════════
SECTION 3: STYLE REQUIREMENTS
═══════════════════════════════════════════════════════════════

3.1 VOICE
  • Write as a human domain expert. First-person where natural:
    "I've seen claims teams..." / "I've reviewed dozens of..."
  • Use active voice. "The system saves results" not "results are saved."
  • Use "is/are/has" not "serves as/stands as/boasts/represents."
  • Take a stance. Don't hedge. If something is overhyped, say so:
    "this vendor's claims are inflated by 40%" not "some may question accuracy."

3.2 SENTENCE AND PARAGRAPH RHYTHM
  • Vary sentence length aggressively. Never let 3 consecutive sentences
    all fall in the 15-25 word range (the LLM comfort zone).
  • Mix paragraph lengths: 1-2 sentence punches, 4-5 sentence deep dives.
  • Allow some imperfection: half-formed thoughts, brief tangents,
    self-corrections ("Actually, scratch that — the real issue is...").

3.3 INDUSTRY VOICE
  • Use insurance jargon naturally without defining it: loss ratio,
    combined ratio, TPA, MGA, bordereaux, parametric trigger, STP, UW,
    FNOL, LR, COR. Your readers are insurance professionals.
  • Include at least one real trade-off, limitation, or failure mode
    per major section. No puff pieces.

———————————————————————————————————————————————————————————————
SECTION 4: INFORMATION INTEGRITY (CRITICAL — ANTI-HALLUCINATION)
———————————————————————————————————————————————————————————————

4.1 NEVER FABRICATE
  • No G2 star ratings, Capterra scores, Gartner Magic Quadrant positions,
    Forrester Wave scores, IDC MarketScape positions, TrustRadius scores,
    or any vendor comparison matrix number without a specific public source.
  • Every statistical/numerical claim MUST name: source institution + year
    + specific report or project name.
  • Never use "studies show" / "industry reports suggest" / "research
    indicates" / "analysts estimate" as attribution for any numeric claim.

4.2 ATTRIBUTION RULES
  • Vendor claims are NOT independent verification. Attribute explicitly:
    "Hiscox claimed in its June 2022 press release that..." not
    "Hiscox reduced cycle time by 99%."
  • Every article MUST include at least 1 real, clickable external link:
    <a href="https://..." target="_blank" rel="noopener noreferrer">
    [Source Name, Report Title]</a>. URL must point to an actual public page.
  • Cite at least 2 specific data sources per article with org name + year.

4.3 FORBIDDEN CITATION PATTERNS
  • "According to Gartner, the market will reach $X billion by 20XX"
    (no report title)
  • "Rated 4.X/5 on G2 based on X,XXX+ reviews" (behind login wall)
  • "Named a Leader in the 202X Gartner Magic Quadrant" (no publication date)
  • "McKinsey reports that 70% of insurers..." (no year + report name)

———————————————————————————————————————————————————————————————
SECTION 5: ARTICLE STRUCTURE
———————————————————————————————————————————————————————————————

5.1 OPENING
  • MUST start with one of: a specific dollar figure or percentage, a named
    company's specific result, a regulatory event with date, or a contrarian
    claim that challenges conventional wisdom.
  • NEVER open with: rhetorical question, broad industry observation,
    "In the world of insurance...", or background/context fluff.

5.2 BODY
  • Use <h2> for 4-6 major sections, <h3> for sub-sections. All headings
    in sentence case.
  • Include at least 1 <table> with minimum 4 rows × 4 columns, comparing
    specific vendors / frameworks / metrics / approaches — not generic pros/cons.
  • No inline bold keyword lists. Rewrite as flowing paragraphs.

5.3 ENDING
  • NO summary / conclusion / "key takeaways" paragraph.
  • End on: a specific forward-looking observation, a hard unanswered
    question, or an actionable next step.
  • No positive-energy sign-off ("The future looks bright" etc.).

———————————————————————————————————————————————————————————————
SECTION 6: PERSPECTIVE REQUIREMENT
———————————————————————————————————————————————————————————————

Pick ONE practitioner perspective and maintain it throughout:
  • Claims Adjuster / FNOL Specialist (operational, on-the-ground)
  • CTO / VP of Engineering (build-vs-buy, architecture, integration)
  • CFO / Head of FP&A (ROI, unit economics, cost modeling)
  • Chief Compliance Officer / General Counsel (regulatory risk, governance)
  • Product Manager at an MGA (launch velocity, market fit)
  • Data Science Lead (model governance, data quality, feature engineering)

The perspective must be identifiable within the first 3 paragraphs and
shape which metrics are prioritized, which trade-offs get scrutiny, and
what the actionable takeaway is. Do NOT write from a generic "industry
analyst" voice.

———————————————————————————————————————————————————————————————
SECTION 7: OUTPUT FORMAT
———————————————————————————————————————————————————————————————

  • Raw HTML for Jinja2 {{ content }} block insertion.
  • Use <h2>, <h3>, <p>, <ul>/<li>, <table>/<thead>/<tbody>/<th>/<td>.
  • NO <!DOCTYPE>, <html>, <head>, <body> tags.
  • NO code fences (```html or otherwise).
  • Word count: adhere strictly to the range. Minimum 1200 for all types.""")

TYPE_INSTRUCTIONS = {
    "tutorial": "Write a step-by-step implementation guide. Include numbered steps, code snippets or config examples where relevant, and a realistic resource estimate. Target: practitioner who will actually build this.",
    "tool-review": "Write a hands-on tool review. Cover: what it does, pricing, setup experience, what it does well, where it falls short. No star ratings — qualitative only.",
    "news": "Write a news analysis piece. Lead with the event, then provide context, market reaction, and a contrarian take. Short, punchy.",
    "comparison": "Build a comparison table (<table>) of 4-6 options, then analyze trade-offs. Explicitly recommend which to pick for which scenario.",
    "explainer": "Explain a complex concept to a mid-level insurance professional. Assume domain knowledge — skip the basics. Lead with a provocative question or stat.",
    "case-study": "Profile a real company's implementation. Structure: Background → Challenge → Solution → Results → Lessons Learned. Use actual numbers.",
    "how-to": "Practical, actionable guide. Start with the end result, then show exactly how to get there. Include pitfalls and shortcuts.",
}


def build_user_prompt(keyword: str, content_type: str) -> str:
    min_words, max_words = CONTENT_LENGTH_RULES.get(content_type, (1200, 2500))
    type_instruction = TYPE_INSTRUCTIONS.get(content_type, TYPE_INSTRUCTIONS["explainer"])

    return textwrap.dedent(f"""\
Content Type: {content_type}
Target Keyword: {keyword}
Word Count Range: {min_words}-{max_words} words

{type_instruction}

Generate the article now. Start directly with the HTML content — no preamble, no meta-commentary, no code fences.""")


def generate_article(keyword_entry, config) -> str:
    """Generate HTML body content for one article."""
    gen_cfg = config["generation"]

    raw = generate_text(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=build_user_prompt(keyword_entry["keyword"], keyword_entry["type"]),
        temperature=gen_cfg.get("temperature", 0.7),
        max_tokens=gen_cfg.get("max_tokens", 4096),
        retry_attempts=gen_cfg.get("retry_attempts", 3),
        retry_delays=gen_cfg.get("retry_delay_seconds", [5, 15, 30]),
    )

    # Safety net: strip ```html fences and chatbot preamble if LLM ignored
    # the "NO code fences" instruction in the system prompt
    raw = _clean_llm_body_response(raw)

    return raw


# ---------------------------------------------------------------------------
# Post-processing
# ---------------------------------------------------------------------------

def extract_title(html_content: str) -> str:
    """Extract first <h[12]> as title."""
    m = re.search(r"<h[12]>(.+?)</h[12]>", html_content)
    if m:
        return m.group(1).strip()
    return "Untitled"


def generate_description(html_content: str, max_chars: int = 160) -> str:
    """Extract first meaningful <p> as meta description."""
    m = re.search(r"<p>(.+?)</p>", html_content)
    if m:
        desc = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        return desc[:max_chars].rsplit(" ", 1)[0] + ("..." if len(desc) > max_chars else "")
    return ""


def make_slug(title: str) -> str:
    slug = title.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:80].strip("-")


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def split_content_at_third(html_body: str) -> tuple:
    """Split HTML content at approximately 1/3 mark, at a paragraph boundary."""
    paragraphs = re.findall(r'<p>.*?</p>', html_body, re.DOTALL)
    if len(paragraphs) < 4:
        return html_body, ""

    split_idx = max(1, len(paragraphs) // 3)

    search_start = 0
    for i, para in enumerate(paragraphs):
        idx = html_body.find(para, search_start)
        if idx < 0:
            return html_body, ""
        if i >= split_idx:
            first = html_body[:idx]
            rest = html_body[idx:]
            return first.strip(), rest.strip()
        search_start = idx + len(para)

    return html_body, ""


def render_article(config, keyword_entry, html_body: str) -> Path:
    """Render one article to content/{subdomain}/{slug}/index.html"""
    jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

    # Post-process: add target="_blank" rel="noopener noreferrer" to external links
    def _fix_external_link(m):
        tag = m.group(0)
        if 'target=' in tag:
            return tag
        return tag.replace('<a ', '<a target="_blank" rel="noopener noreferrer" ')

    html_body = re.sub(r'<a\s[^>]*href="https?://[^"]*"[^>]*>', _fix_external_link, html_body)

    # Add loading="lazy" and width/height to img tags
    def _fix_img(m):
        tag = m.group(0)
        src_match = re.search(r'src="([^"]*)"', tag)
        if not src_match:
            return tag
        src = src_match.group(1)
        # Add loading="lazy" if missing
        if 'loading=' not in tag.lower():
            tag = tag.replace('<img ', '<img loading="lazy" ')
        # Add width/height if missing
        if 'width=' not in tag.lower() or 'height=' not in tag.lower():
            w, h = get_image_dimensions(src)
            tag = re.sub(r'\s(width|height)="[^"]*"', '', tag)
            tag = tag.replace('<img ', f'<img width="{w}" height="{h}" ')
        return tag

    html_body = re.sub(r'<img\s[^>]*>', _fix_img, html_body)

    title = extract_title(html_body)
    description = generate_description(html_body)
    slug = make_slug(title)
    subdomain = keyword_entry["subdomain"]
    sd_names = {sd["slug"]: sd["name"] for sd in config["subdomains"]}
    subdomain_name = sd_names.get(subdomain, subdomain.replace("-", " ").title())

    now = datetime.now(timezone.utc)
    date_iso = now.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    date_display = now.strftime("%B %d, %Y")

    adsense = config.get("adsense", {})
    pub_id = adsense.get("pub_id", "")
    ad_slots = adsense.get("ad_units", {})

    # ── ROOT-CAUSE FIX: HTML <head> pollution ─────────────────────────────────
    # Previously the FULL rendered HTML document (including the <head> with the
    # title / meta description / canonical / Open Graph tags) was handed to the
    # LLM, and Pass 2's "Output the complete enhanced article" instruction made
    # the model rewrite or drop the <head> — producing pages with a destroyed or
    # missing <head> (the 34 broken articles seen in the Aug 2026 cleanup).
    #
    # We now enhance ONLY the article BODY, then re-render the template, so the
    # <head> is always the pristine template output and can never be corrupted by
    # the LLM. As a safety net we also strip any code fences / chatbot preamble /
    # stray full-document wrapper that the model might still return.
    os.environ.setdefault("MISTRAL_API_KEY", "DaqhV9nv9V228XEPUWm52Rqsj8rpJbS4")
    v2_result = enhance_article(html_body)
    enhanced_body = v2_result["enhanced_text"]
    enhanced_body = _clean_llm_body_response(enhanced_body) if enhanced_body else ""
    if not enhanced_body or len(enhanced_body) < 200:
        logger.warning(
            "enhance_article returned unusable body (len=%d) — falling back to clean body. "
            "stance=%s, personas=%s",
            len(enhanced_body) if enhanced_body else 0,
            v2_result["stance_used"], v2_result["personas_used"]
        )
        enhanced_body = html_body

    content_first, content_rest = split_content_at_third(enhanced_body)

    # 社区视角区块：按子域名路由抓取真人讨论（带缓存 + 开关，默认关闭）。
    community_section = ""
    if build_community_section is not None:
        try:
            community_section = build_community_section(
                subdomain, title, slug, keyword_entry.get("keyword", ""))
        except Exception as e:
            logger.warning("community section skipped: %s", e)
            community_section = ""

    html = jinja_env.get_template("article.html").render(
        site_name=config["site"]["name"],
        subdomains=config["subdomains"],
        current_year=now.year,
        current_date=date_display,
        title=title,
        description=description,
        keyword=keyword_entry["keyword"],
        content_first=content_first,
        content_rest=content_rest,
        community_section=community_section,
        date_iso=date_iso,
        date_display=date_display,
        subdomain=subdomain,
        subdomain_name=subdomain_name,
        adsense_pub_id=pub_id or None,
        ad_slot_top=ad_slots.get("top_banner", {}).get("slot", ""),
        ad_slot_in=ad_slots.get("in_content", {}).get("slot", ""),
        ad_slot_bottom=ad_slots.get("bottom", {}).get("slot", ""),
        canonical_url=f"/{subdomain}/{slug}/",
        ga_id=config.get("analytics", {}).get("ga_id", ""),
    )

    # Apply de-AI post-processing to disrupt LLM-detectable patterns
    html = deai_process(html)

    logger.info("enhance_article: stance=%s, personas=%s, llm=%s",
                v2_result["stance_used"], v2_result["personas_used"], v2_result["llm_called"])

    out_dir = CONTENT_DIR / subdomain / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "index.html"
    out_file.write_text(html, encoding="utf-8")
    inject_widget(out_file)
    inject_csp(out_file)

    logger.info("Rendered: %s", out_file)
    return out_file, slug, title, description, subdomain_name, date_display


# ---------------------------------------------------------------------------
# Index & Sitemap
# ---------------------------------------------------------------------------

def _collect_all_articles() -> list:
    """Scan content/ for all published articles, enriched with index.json metadata."""
    # Build lookup from index.json for date_display and generated_at
    index_lookup = {}
    index_path = CONTENT_DIR / "index.json"
    if index_path.exists():
        entries = json.loads(index_path.read_text(encoding="utf-8"))
        for e in entries:
            url = e.get("url", "")
            index_lookup[url] = {
                "date_display": e.get("date_display", ""),
                "generated_at": e.get("generated_at", ""),
            }

    articles = []
    for sf in CONTENT_DIR.iterdir():
        if not sf.is_dir():
            continue
        for af in sf.iterdir():
            if af.is_dir() and (af / "index.html").exists():
                html = (af / "index.html").read_text(encoding="utf-8")
                title = extract_title(html)
                desc = generate_description(html)
                url = f"/{sf.name}/{af.name}/"
                meta = index_lookup.get(url, {})
                articles.append({
                    "url": url,
                    "title": title,
                    "description": desc,
                    "subdomain": sf.name,
                    "slug": af.name,
                    "subdomain_name": sf.name.replace("-", " ").title(),
                    "date_display": meta.get("date_display", ""),
                    "generated_at": meta.get("generated_at", ""),
                })
    articles.sort(key=lambda a: a["generated_at"] or a["url"], reverse=True)
    return articles


def rebuild_rss(config) -> None:
    """Generate /content/rss.xml (RSS 2.0 feed)."""
    domain = config["site"].get("domain", "821224.com")
    site_name = config["site"]["name"]
    articles = _collect_all_articles()

    items_xml = []
    for a in articles:
        title = a.get("title", "")
        url = a.get("url", "")
        description = a.get("description", "")
        subdomain_name = a.get("subdomain_name", a.get("subdomain", ""))
        date_display = a.get("date_display", "")

        # Parse date_display ("May 12, 2026") → RFC 822
        pub_date = ""
        if date_display:
            try:
                dt = datetime.strptime(date_display, "%B %d, %Y")
                dt = dt.replace(tzinfo=timezone.utc)
                pub_date = format_datetime(dt, usegmt=True)
            except ValueError:
                pass
        if not pub_date:
            pub_date = format_datetime(datetime.now(timezone.utc), usegmt=True)

        # Truncate description to 300 chars
        desc = description[:300] if description else ""
        if len(description or "") > 300:
            desc = desc.rsplit(" ", 1)[0] + "..."

        items_xml.append(
            "<item>\n"
            f"      <title>{escape_xml(title)}</title>\n"
            f"      <link>https://{domain}{url}</link>\n"
            f"      <description>{escape_xml(desc)}</description>\n"
            f"      <pubDate>{pub_date}</pubDate>\n"
            f"      <guid isPermaLink=\"true\">https://{domain}{url}</guid>\n"
            f"      <category>{escape_xml(subdomain_name)}</category>\n"
            f"    </item>"
        )

    now = format_datetime(datetime.now(timezone.utc), usegmt=True)

    rss = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "  <channel>\n"
        f"    <title>{escape_xml(site_name)}</title>\n"
        f"    <link>https://{domain}</link>\n"
        f"    <description>In-depth coverage of how artificial intelligence is reshaping insurance — from claims automation to underwriting intelligence.</description>\n"
        f"    <language>en-us</language>\n"
        f"    <lastBuildDate>{now}</lastBuildDate>\n"
        f'    <atom:link href="https://{domain}/rss.xml" rel="self" type="application/rss+xml"/>\n'
        + "\n".join(items_xml) + "\n"
        "  </channel>\n"
        "</rss>\n"
    )

    (CONTENT_DIR / "rss.xml").write_text(rss, encoding="utf-8")
    logger.info("Generated RSS feed with %d items.", len(items_xml))


def rebuild_home(config) -> None:
    """Rebuild /content/index.html with one article per subdomain + one extra (7 total)."""
    import random as _random
    _random.seed(42)  # deterministic per build
    jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    all_articles = _collect_all_articles()
    total_count = len(all_articles)

    # Group articles by subdomain
    by_sd = {}
    for a in all_articles:
        by_sd.setdefault(a["subdomain"], []).append(a)

    # Pick one random article per subdomain (6 total)
    picked = []
    for sd_slug in sorted(by_sd.keys()):
        picked.append(_random.choice(by_sd[sd_slug]))

    # Pick one extra random article from any subdomain (different from the 6)
    picked_urls = {a["url"] for a in picked}
    remaining = [a for a in all_articles if a["url"] not in picked_urls]
    if remaining:
        picked.append(_random.choice(remaining))

    _random.shuffle(picked)

    adsense = config.get("adsense", {})
    pub_id = adsense.get("pub_id", "")

    html = jinja_env.get_template("home.html").render(
        site_name=config["site"]["name"],
        subdomains=config["subdomains"],
        current_year=datetime.now(timezone.utc).year,
        articles=picked,
        canonical_url="/",
        adsense_pub_id=pub_id or None,
        ad_slot_top="",
        ga_id=config.get("analytics", {}).get("ga_id", ""),
        is_category_page=False,
        show_hero_ad=False,
        current_category_slug="",
        hero_badge_text="Sharp Insights Provided",
        hero_heading="AI meets Insurance<br>Technology",
        hero_subtitle_text="In-depth coverage of how artificial intelligence is reshaping insurance — from claims automation to underwriting intelligence.",
        total_articles_count=total_count,
        section_title="Most Viewed Articles",
        pagination=None,
    )
    (CONTENT_DIR / "index.html").write_text(html, encoding="utf-8")
    inject_widget(CONTENT_DIR / "index.html")
    inject_csp(CONTENT_DIR / "index.html")
    logger.info("Rebuilt home page with %d articles (total: %d).", len(picked), total_count)


def rebuild_sitemap(config) -> None:
    """Rebuild /content/sitemap.xml."""
    domain = config["site"].get("domain", "YOUR_DOMAIN")
    articles = _collect_all_articles()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    lines.append(f"  <url><loc>https://{domain}/</loc><lastmod>{now}</lastmod><priority>1.0</priority></url>")
    # Static pages
    for page in ["about", "contact", "privacy", "terms"]:
        lines.append(f"  <url><loc>https://{domain}/{page}/</loc><lastmod>{now}</lastmod><priority>0.5</priority></url>")
    # Subdomain category pages
    for sd in config["subdomains"]:
        lines.append(f"  <url><loc>https://{domain}/{sd['slug']}/</loc><lastmod>{now}</lastmod><priority>0.8</priority></url>")
    # Articles
    for art in articles:
        lines.append(f"  <url><loc>https://{domain}{art['url']}</loc><lastmod>{now}</lastmod><priority>0.9</priority></url>")
    lines.append("</urlset>")

    (CONTENT_DIR / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Rebuilt sitemap.xml with %d URLs.", len(articles) + 5 + len(config["subdomains"]))


def rebuild_html_sitemap(config) -> None:
    """Rebuild /content/sitemap/index.html — HTML sitemap organized by category."""
    jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    all_articles = _collect_all_articles()

    sd_names = {sd["slug"]: sd["name"] for sd in config["subdomains"]}
    articles_by_sd = {}
    for sd in config["subdomains"]:
        articles_by_sd[sd["slug"]] = [
            a for a in all_articles if a["subdomain"] == sd["slug"]
        ]

    html = jinja_env.get_template("sitemap.html").render(
        site_name=config["site"]["name"],
        subdomains=config["subdomains"],
        current_year=datetime.now(timezone.utc).year,
        articles_by_sd=articles_by_sd,
        sd_names=sd_names,
        canonical_url="/sitemap/",
        ga_id=config.get("analytics", {}).get("ga_id", ""),
    )

    out_dir = CONTENT_DIR / "sitemap"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    inject_widget(out_dir / "index.html")
    inject_csp(out_dir / "index.html")
    logger.info("Rebuilt HTML sitemap with %d articles across %d categories.", len(all_articles), len(config["subdomains"]))


def rebuild_index_json(articles_meta: list) -> None:
    """Append new articles to index.json for future related-article linking."""
    index_path = CONTENT_DIR / "index.json"
    existing = []
    if index_path.exists():
        existing = json.loads(index_path.read_text(encoding="utf-8"))
    existing.extend(articles_meta)
    index_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Category index pages
# ---------------------------------------------------------------------------

def rebuild_category_pages(config) -> None:
    """Generate index.html (and pageN.html) for each subdomain category, sorted by date."""
    import math
    jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    all_articles = _collect_all_articles()
    total_count = len(all_articles)
    adsense = config.get("adsense", {})
    pub_id = adsense.get("pub_id", "")
    ad_slots = adsense.get("ad_units", {})
    PAGE_SIZE = 10

    for sd in config["subdomains"]:
        slug = sd["slug"]
        cat_articles = [a for a in all_articles if a["url"].startswith(f"/{slug}/")]
        # Already sorted by generated_at from _collect_all_articles
        cat_articles.sort(key=lambda a: a["generated_at"] or "", reverse=True)

        hero = CATEGORY_HERO.get(slug, {
            "badge": sd.get("name", slug),
            "heading": sd.get("name", slug),
            "subtitle": ""
        })

        base_url = f"/{slug}/"
        total_pages = max(1, math.ceil(len(cat_articles) / PAGE_SIZE))

        for page in range(1, total_pages + 1):
            start = (page - 1) * PAGE_SIZE
            end = start + PAGE_SIZE
            page_articles = cat_articles[start:end]

            pagination = {
                "current_page": page,
                "total_pages": total_pages,
                "base_url": base_url,
            }

            html = jinja_env.get_template("home.html").render(
                site_name=f"{sd['name']} — {config['site']['name']}",
                subdomains=config["subdomains"],
                current_year=datetime.now(timezone.utc).year,
                articles=page_articles,
                canonical_url=f"/{slug}/",
                adsense_pub_id=pub_id or None,
                ad_slot_top=ad_slots.get("top_banner", {}).get("slot", ""),
                ga_id=config.get("analytics", {}).get("ga_id", ""),
                is_category_page=True,
                show_hero_ad=True,
                current_category_slug=slug,
                hero_badge_text=hero["badge"],
                hero_heading=hero["heading"],
                hero_subtitle_text=hero["subtitle"],
                total_articles_count=len(cat_articles),
                section_title="Latest Articles",
                pagination=pagination,
                category_meta_description=CATEGORY_META_DESCRIPTIONS.get(slug, ""),
            )

            out_dir = CONTENT_DIR / slug
            out_dir.mkdir(parents=True, exist_ok=True)
            if page == 1:
                (out_dir / "index.html").write_text(html, encoding="utf-8")
                inject_widget(out_dir / "index.html")
                inject_csp(out_dir / "index.html")
            else:
                (out_dir / f"page{page}.html").write_text(html, encoding="utf-8")

        logger.info("Rebuilt category page: /%s/ (%d articles, %d pages)", slug, len(cat_articles), total_pages)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Insurtech Insights Content Generator")
    parser.add_argument("--count", type=int, default=1, help="Number of articles to generate")
    parser.add_argument("--rebuild", action="store_true", help="Only rebuild site infrastructure (home, categories, sitemaps)")
    args = parser.parse_args()

    config = load_config()

    if args.rebuild:
        logger.info("Rebuild-only mode: regenerating home, category pages, sitemaps, and RSS.")
        rebuild_home(config)
        rebuild_rss(config)
        rebuild_sitemap(config)
        rebuild_html_sitemap(config)
        rebuild_category_pages(config)
        logger.info("Rebuild complete.")
        return

    logger.info("Site: %s | Articles requested: %d", config["site"]["name"], args.count)

    # Pick keywords
    selected = pick_unused_keywords(config, args.count)
    if not selected:
        logger.error("No unused keywords remaining. Add more to keywords/*.json")
        sys.exit(1)
    logger.info("Selected %d keywords from pool.", len(selected))

    # Mark all selected keywords as pending BEFORE generation
    # to prevent concurrent runs from picking the same keywords
    for kw in selected:
        mark_pending(kw)

    articles_meta = []

    for i, kw in enumerate(selected, 1):
        logger.info("[%d/%d] Generating: %s (%s)", i, len(selected), kw["keyword"], kw["type"])
        try:
            html_body = generate_article(kw, config)
        except Exception as exc:
            logger.error("Failed to generate '%s': %s", kw["keyword"], exc)
            continue

        try:
            out_file, slug, title, description, sd_name, date_display = render_article(config, kw, html_body)
        except Exception as exc:
            logger.error("Failed to render '%s': %s", kw["keyword"], exc)
            continue

        mark_completed(kw)
        articles_meta.append({
            "keyword": kw["keyword"],
            "type": kw["type"],
            "subdomain": kw["subdomain"],
            "url": f"/{kw['subdomain']}/{slug}/",
            "title": title,
            "description": description,
            "subdomain_name": sd_name,
            "date_display": date_display,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        })

    # Post-run: rebuild infrastructure
    if articles_meta:
        rebuild_index_json(articles_meta)
        rebuild_home(config)
        rebuild_rss(config)
        rebuild_sitemap(config)
        rebuild_html_sitemap(config)
        rebuild_category_pages(config)

    logger.info("Done. Generated %d/%d articles successfully.", len(articles_meta), len(selected))


if __name__ == "__main__":
    main()