#!/usr/bin/env python3
"""
citation_check.py — Citation Verification Module (手段5)
========================================================
Cross-references citations in articles against a pre-loaded database of
15 verified industry reports, plus fuzzy matching against known publishers.

Usage:
    from pipeline.citation_check import check_citations
    report = check_citations(article_text)
"""

import re
import logging
from datetime import datetime

logger = logging.getLogger("citation_check")

# ---------------------------------------------------------------------------
# 15 Verified Industry Reports (pre-loaded ground truth)
# ---------------------------------------------------------------------------
# Each entry: short_name, full_citation, publisher, year, url (if known), aliases/keywords

VERIFIED_SOURCES = [
    {
        "id": "SRC001",
        "name": "McKinsey Global Insurance Report 2024",
        "publisher": "McKinsey & Company",
        "year": 2024,
        "url": "https://www.mckinsey.com/industries/financial-services/our-insights/global-insurance-report-2024",
        "keywords": ["mckinsey", "global insurance report", "insurance 2024"],
    },
    {
        "id": "SRC002",
        "name": "Deloitte Insurance Outlook 2025",
        "publisher": "Deloitte",
        "year": 2025,
        "url": "https://www2.deloitte.com/us/en/pages/financial-services/articles/insurance-industry-outlook.html",
        "keywords": ["deloitte", "insurance outlook", "insurance 2025"],
    },
    {
        "id": "SRC003",
        "name": "Accenture Technology Vision for Insurance 2024",
        "publisher": "Accenture",
        "year": 2024,
        "url": "https://www.accenture.com/us-en/insights/insurance/technology-vision-insurance",
        "keywords": ["accenture", "technology vision", "insurance technology"],
    },
    {
        "id": "SRC004",
        "name": "Gartner Hype Cycle for Insurance 2024",
        "publisher": "Gartner",
        "year": 2024,
        "url": "https://www.gartner.com/en/industries/insurance",
        "keywords": ["gartner", "hype cycle", "insurance technology hype"],
    },
    {
        "id": "SRC005",
        "name": "NAIC AI Principles for Insurance 2024",
        "publisher": "NAIC (National Association of Insurance Commissioners)",
        "year": 2024,
        "url": "https://content.naic.org/cipr-topics/artificial-intelligence",
        "keywords": ["naic", "ai principles", "insurance regulation", "insurance commissioners"],
    },
    {
        "id": "SRC006",
        "name": "EIOPA Artificial Intelligence Governance Guidelines",
        "publisher": "EIOPA (European Insurance and Occupational Pensions Authority)",
        "year": 2024,
        "url": "https://www.eiopa.europa.eu/browse/regulation-and-policy/digitalisation-and-financial-innovation_en",
        "keywords": ["eiopa", "ai guidelines", "ai governance", "european insurance"],
    },
    {
        "id": "SRC007",
        "name": "Swiss Re Sigma Report: World Insurance 2024",
        "publisher": "Swiss Re Institute",
        "year": 2024,
        "url": "https://www.swissre.com/institute/research/sigma-research.html",
        "keywords": ["swiss re", "sigma", "world insurance", "global premiums"],
    },
    {
        "id": "SRC008",
        "name": "CB Insights Insurtech 50 (2025)",
        "publisher": "CB Insights",
        "year": 2025,
        "url": "https://www.cbinsights.com/research/report/insurtech-50-2025/",
        "keywords": ["cb insights", "insurtech 50", "insurtech startups"],
    },
    {
        "id": "SRC009",
        "name": "Willis Towers Watson Insurtech Quarterly Briefing Q1 2025",
        "publisher": "WTW (Willis Towers Watson)",
        "year": 2025,
        "url": "https://www.wtwco.com/en-us/insights",
        "keywords": ["wtw", "willis towers watson", "insurtech quarterly", "insurtech briefing"],
    },
    {
        "id": "SRC010",
        "name": "Verisk Claims Efficiency Study 2023",
        "publisher": "Verisk Analytics",
        "year": 2023,
        "url": "https://www.verisk.com/insurance/claims/claims-efficiency-study-2023",
        "keywords": ["verisk", "claims efficiency", "claims study", "auto claims"],
    },
    {
        "id": "SRC011",
        "name": "ISO Claims Survey 2023",
        "publisher": "ISO (Insurance Services Office)",
        "year": 2023,
        "url": "https://www.iso.com/products/claims-survey-2023",
        "keywords": ["iso", "claims survey", "insurance claims survey"],
    },
    {
        "id": "SRC012",
        "name": "CAS Reserving Dataset 2023",
        "publisher": "CAS (Casualty Actuarial Society)",
        "year": 2023,
        "url": "https://www.casact.org/research",
        "keywords": ["cas", "reserving", "loss reserve", "actuarial"],
    },
    {
        "id": "SRC013",
        "name": "Lemonade Q4 2023 Investor Relations",
        "publisher": "Lemonade Inc.",
        "year": 2023,
        "url": "https://investors.lemonade.com/",
        "keywords": ["lemonade", "q4 2023", "investor relations", "lemonade results"],
    },
    {
        "id": "SRC014",
        "name": "Allstate Annual Report 2023 / AI Fraud Savings",
        "publisher": "Allstate Corporation",
        "year": 2024,
        "url": "https://www.allstateinvestors.com/",
        "keywords": ["allstate", "fraud detection", "annual report", "ai savings"],
    },
    {
        "id": "SRC015",
        "name": "Guidewire Analytics Benchmarking Report 2024",
        "publisher": "Guidewire Software",
        "year": 2024,
        "url": "https://www.guidewire.com/resources/analytics-benchmarking",
        "keywords": ["guidewire", "analytics benchmarking", "claims analytics"],
    },
]

# ---------------------------------------------------------------------------
# 4 Citation Extraction Regex Patterns
# ---------------------------------------------------------------------------

CITATION_PATTERNS = [
    # Pattern 1: Bracketed format [Source Name, Year] or [Source Name]
    re.compile(
        r'\[([^\]]+?)\]',
        re.IGNORECASE,
    ),
    # Pattern 2: Inline reference: "According to Source (Year)..."
    re.compile(
        r'(?:according\s+to|per|reported\s+by|data\s+from|cited\s+in|published\s+by)\s+'
        r'([A-Z][A-Za-z\s&\.,]+?(?:\d{4})?(?:[A-Za-z\s]*?))',
        re.IGNORECASE,
    ),
    # Pattern 3: Hyperlinked citations: [text](url)
    re.compile(
        r'\[([^\]]+)\]\(([^)]+)\)',
        re.IGNORECASE,
    ),
    # Pattern 4: "SourceName (Year)" format in running text
    re.compile(
        r'([A-Z][A-Za-z\s]+(?:&amp;|&|and)?\s*[A-Za-z\s]*?)\s*\((\d{4})\)',
        re.IGNORECASE,
    ),
]

# ---------------------------------------------------------------------------
# Fuzzy matching
# ---------------------------------------------------------------------------

def _fuzzy_match_citation(citation_text: str) -> dict:
    """Attempt to match a citation string against verified sources."""
    import difflib

    text_lower = citation_text.lower().strip()

    # Direct keyword matching first
    best_score = 0.0
    best_source = None

    for src in VERIFIED_SOURCES:
        # Check publisher name
        pub_lower = src["publisher"].lower()
        if pub_lower in text_lower or text_lower in pub_lower:
            similarity = 0.9
        else:
            similarity = 0.0

        # Check report name
        name_lower = src["name"].lower()
        name_sim = difflib.SequenceMatcher(None, text_lower, name_lower).ratio()
        similarity = max(similarity, name_sim)

        # Check keywords
        for kw in src["keywords"]:
            kw_lower = kw.lower()
            if kw_lower in text_lower:
                similarity = max(similarity, 0.85)
            kw_sim = difflib.SequenceMatcher(None, text_lower, kw_lower).ratio()
            similarity = max(similarity, kw_sim)

        if similarity > best_score:
            best_score = similarity
            best_source = src

    if best_source and best_score >= 0.6:
        return {
            "status": "verified" if best_score >= 0.85 else "needs_fix",
            "matched_source": best_source["name"],
            "source_id": best_source["id"],
            "confidence": round(best_score, 2),
            "url": best_source.get("url", ""),
        }
    else:
        return {
            "status": "not_verified" if best_score and best_score >= 0.3 else "fabricated",
            "matched_source": best_source["name"] if best_source else None,
            "source_id": best_source["id"] if best_source else None,
            "confidence": round(best_score, 2),
            "url": "",
        }


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def check_citations(article_text: str, article_title: str = "") -> dict:
    """
    Extract and verify all citations in an article.

    Args:
        article_text: Plain text or HTML content of the article.
        article_title: Article title for reporting.

    Returns:
        dict with keys:
            - total_citations: int
            - verified: list of verified citation dicts
            - not_verified: list of unverifiable citation dicts
            - needs_fix: list of citations needing correction
            - fabricated: list of likely fabricated citations
            - summary: dict with counts by status
            - article_title: str
    """
    # Strip HTML tags for plain text analysis
    plain = re.sub(r'<[^>]+>', ' ', article_text)
    plain = re.sub(r'\s+', ' ', plain).strip()

    all_citations = []

    # Extract using all patterns
    for pattern in CITATION_PATTERNS:
        for match in pattern.finditer(plain):
            citation_text = match.group(0).strip()
            # Skip very short matches and common non-citation brackets
            if len(citation_text) < 10:
                continue
            # Skip HTML/JS code-like brackets
            if citation_text.startswith('<') or '{' in citation_text:
                continue
            # Skip common non-citation patterns
            skip_patterns = ['adsbygoogle', 'window.', 'function', 'gtag', 'utm_',
                           'javascript:', 'css', 'padding', 'margin', 'font-']
            if any(s in citation_text.lower() for s in skip_patterns):
                continue
            all_citations.append(citation_text)

    # Deduplicate
    seen = set()
    unique_citations = []
    for c in all_citations:
        normalized = c.lower().strip()[:100]
        if normalized not in seen:
            seen.add(normalized)
            unique_citations.append(c)

    # Verify each
    verified = []
    not_verified = []
    needs_fix = []
    fabricated = []

    for citation in unique_citations:
        result = _fuzzy_match_citation(citation)
        result["raw_citation"] = citation

        if result["status"] == "verified":
            verified.append(result)
        elif result["status"] == "needs_fix":
            needs_fix.append(result)
        elif result["status"] == "not_verified":
            not_verified.append(result)
        else:
            fabricated.append(result)

    total = len(unique_citations)
    summary = {
        "total": total,
        "verified": len(verified),
        "not_verified": len(not_verified),
        "needs_fix": len(needs_fix),
        "fabricated": len(fabricated),
        "verification_rate": round(len(verified) / total * 100, 1) if total > 0 else 0,
    }

    return {
        "article_title": article_title,
        "total_citations": total,
        "verified": verified,
        "not_verified": not_verified,
        "needs_fix": needs_fix,
        "fabricated": fabricated,
        "summary": summary,
        "checked_at": datetime.now().isoformat(),
    }


# ---------------------------------------------------------------------------
# Format report for bulk output
# ---------------------------------------------------------------------------

def format_batch_report(results: list) -> str:
    """Format a list of check_citations results into a readable report."""
    lines = []
    lines.append("# Citation Verification Batch Report")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # Aggregate stats
    total_articles = len(results)
    total_citations = sum(r["summary"]["total"] for r in results)
    total_verified = sum(r["summary"]["verified"] for r in results)
    total_not_verified = sum(r["summary"]["not_verified"] for r in results)
    total_needs_fix = sum(r["summary"]["needs_fix"] for r in results)
    total_fabricated = sum(r["summary"]["fabricated"] for r in results)

    lines.append("## Overall Summary")
    lines.append(f"- Articles checked: {total_articles}")
    lines.append(f"- Total citations found: {total_citations}")
    lines.append(f"- Verified: {total_verified} ({round(total_verified/total_citations*100,1)}%)" if total_citations else "- Verified: 0")
    lines.append(f"- Not verified: {total_not_verified} ({round(total_not_verified/total_citations*100,1)}%)" if total_citations else "- Not verified: 0")
    lines.append(f"- Needs fix: {total_needs_fix}")
    lines.append(f"- Fabricated: {total_fabricated}")
    lines.append("")

    # Per-article breakdown
    lines.append("## Per-Article Breakdown")
    lines.append("")

    for r in results:
        s = r["summary"]
        lines.append(f"### {r['article_title'][:80]}")
        lines.append(f"- Total: {s['total']} | Verified: {s['verified']} | Not verified: {s['not_verified']} | Needs fix: {s['needs_fix']} | Fabricated: {s['fabricated']}")

        if r["fabricated"]:
            lines.append("- **FABRICATED:**")
            for fb in r["fabricated"][:5]:
                lines.append(f"  - `{fb['raw_citation'][:120]}`")
        if r["needs_fix"]:
            lines.append("- **NEEDS FIX:**")
            for nf in r["needs_fix"][:3]:
                lines.append(f"  - `{nf['raw_citation'][:120]}` → {nf.get('matched_source', 'N/A')}")
        lines.append("")

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from pathlib import Path

    if len(sys.argv) < 2:
        print("Usage: python citation_check.py <article_html_path>")
        sys.exit(1)

    article_path = Path(sys.argv[1])
    if not article_path.exists():
        print(f"Error: file not found: {article_path}")
        sys.exit(1)

    html = article_path.read_text(encoding='utf-8')
    title = article_path.parent.name[:60]

    result = check_citations(html, title)
    s = result["summary"]

    print(f"Article: {title}")
    print(f"Total citations: {s['total']}")
    print(f"Verified: {s['verified']} | Not verified: {s['not_verified']} | Needs fix: {s['needs_fix']} | Fabricated: {s['fabricated']}")
    print(f"Verification rate: {s['verification_rate']}%")

    if result["fabricated"]:
        print("\n--- Fabricated ---")
        for fb in result["fabricated"]:
            print(f"  {fb['raw_citation'][:120]}")
    if result["needs_fix"]:
        print("\n--- Needs Fix ---")
        for nf in result["needs_fix"]:
            print(f"  {nf['raw_citation'][:120]} → {nf.get('matched_source', 'N/A')}")

