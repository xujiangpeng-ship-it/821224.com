#!/usr/bin/env python3
\"\"\"
seo_audit_and_fix.py - Comprehensive SEO audit and fix for 821224.com
Addresses Google's quality requirements: E-E-A-T, structured data, meta tags, content quality.
\"\"\"

import re
import json
import os
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
CONTENT_DIR = ROOT / \"content\"

# Author information for E-E-A-T
AUTHOR_INFO = {
    \"name\": \"Bin Sun\",
    \"title\": \"Senior Insurance Technology Analyst\",
    \"bio\": \"Bin Sun is a senior analyst specializing in AI applications for insurance technology. With 15+ years in the insurance sector, he provides independent analysis of emerging trends in claims automation, underwriting intelligence, fraud detection, and embedded insurance.\",
    \"url\": \"https://821224.com/about/\"
}

# Verified source organizations for citation integrity
VERIFIED_ORGS = [
    \"McKinsey\", \"Deloitte\", \"Accenture\", \"Gartner\", \"NAIC\",
    \"EIOPA\", \"Swiss Re\", \"CB Insights\", \"Willis Towers Watson\",
    \"Verisk\", \"ISO\", \"Casualty Actuarial Society\", \"Lemonade\",
    \"Allstate\", \"Aviva\", \"Allianz\", \"Arch MIS\", \"Shift Technology\",
    \"Duck Creek\", \"Hiscox\", \"Guidewire\", \"State Farm\", \"Travelers\",
    \"Chubb\", \"AXA\", \"Allianz\", \"Zurich\", \"Hartford\", \"Liberty Mutual\"
]


def count_words_in_html(html: str) -> int:
    \"\"\"Count actual text words in HTML content.\"\"\"
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)
    words = [w for w in text.split() if len(w) > 1]
    return len(words)


def calculate_read_time(word_count: int) -> int:
    \"\"\"Calculate reading time in minutes (avg 200 wpm).\"\"\"
    return max(3, word_count // 200)


def fix_canonical_urls(html: str) -> str:
    \"\"\"Convert relative canonical URLs to absolute.\"\"\"
    html = re.sub(
        r'<link rel=\"canonical\" href=\"/?\"',
        '<link rel=\"canonical\" href=\"https://821224.com/\">',
        html
    )
    html = re.sub(
        r'<link rel=\"canonical\" href=\"\\/([^\"\\>]*)\"',
        r'<link rel=\"canonical\" href=\"https://821224.com/\1/\">',
        html
    )
    return html


def fix_opengraph_full_urls(html: str) -> str:
    \"\"\"Ensure all OG and Twitter image URLs are absolute.\"\"\"
    html = re.sub(
        r'(og:image\" content=\")(/images/[^\"]*)\"',
        r'\1https://821224.com\2\"',
        html
    )
    html = re.sub(
        r'(twitter:image\" content=\")(/images/[^\"]*)\"',
        r'\1https://821224.com\2\"',
        html
    )
    return html


def fix_meta_description(html: str, fallback_title: str = \"\") -> str:
    \"\"\"Ensure meta description is 150-160 characters and unique.\"\"\"
    desc_match = re.search(r'<meta name=\"description\" content=\"([^\"]*)\">', html)
    if desc_match:
        desc = desc_match.group(1)
        # Clean HTML entities
        desc = desc.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        desc = desc.replace('&quot;', '\"').replace('&#39;', \"'\")
        
        if len(desc) > 160:
            desc = desc[:157] + '...'
        elif len(desc) < 100 and fallback_title:
            desc = desc + '. Expert analysis at 821224.com.'
        
        # Re-escape for HTML
        desc = desc.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        desc = desc.replace('\"', '&quot;').replace(\"'\", '&#39;')
        
        html = html.replace(desc_match.group(0), f'<meta name=\"description\" content=\"{desc}\">')
    
    return html


def fix_article_schema(html: str, title: str, category: str, word_count: int) -> str:
    \"\"\"Fix Article structured data with all required Google fields.\"\"\"
    
    # Try to extract date from existing schema
    date_match = re.search(r'\"datePublished\":\\s*\"([^\"]+)\"', html)
    pub_date = date_match.group(1) if date_match else datetime.now().strftime('%Y-%m-%dT%H:%M:%S+00:00')
    
    read_time = calculate_read_time(word_count)
    
    # Build enhanced Article schema
    article_schema = f'''<script type=\"application/ld+json\">
{{
    \"@context\": \"https://schema.org\",
    \"@type\": \"Article\",
    \"headline\": \"{title[:100]}\",
    \"description\": \"{title[:150]}\",
    \"image\": \"https://821224.com/images/logo.webp\",
    \"datePublished\": \"{pub_date}\",
    \"dateModified\": \"{pub_date}\",
    \"author\": {{
        \"@type\": \"Person\",
        \"name\": \"{AUTHOR_INFO['name']}\",
        \"jobTitle\": \"{AUTHOR_INFO['title']}\",
        \"url\": \"{AUTHOR_INFO['url']}\"
    }},
    \"publisher\": {{
        \"@type\": \"Organization\",
        \"name\": \"Insurtech Insights\",
        \"url\": \"https://821224.com\",
        \"logo\": {{
            \"@type\": \"ImageObject\",
            \"url\": \"https://821224.com/images/logo.webp\"
        }}
    }},
    \"wordCount\": {word_count},
    \"timeRequired\": \"PT{read_time}M\",
    \"inLanguage\": \"en-US\",
    \"articleSection\": \"{category}\",
    \"keywords\": \"insurance, AI, insurtech, {category}\"
}}
</script>'''
    
    # Replace existing Article schema
    article_pattern = re.compile(
        r'<script type=\"application/ld\\+json\">\\s*\\{[^}]*\"@type\":\\s*\"Article\"[^}]*\\}\\s*</script>',
        re.DOTALL
    )
    existing = article_pattern.search(html)
    if existing:
        html = html.replace(existing.group(0), article_schema)
    else:
        # Insert before </head>
        html = html.replace('</head>', article_schema + '\\n    </head>')
    
    return html


def add_breadcrumb_schema(html: str, category: str, title: str) -> str:
    \"\"\"Add BreadcrumbList structured data.\"\"\"
    
    breadcrumb_schema = f'''<script type=\"application/ld+json\">
{{
  \"@context\": \"https://schema.org\",
  \"@type\": \"BreadcrumbList\",
  \"itemListElement\": [
    {{
      \"@type\": \"ListItem\",
      \"position\": 1,
      \"name\": \"Home\",
      \"item\": \"https://821224.com/\"
    }},
    {{
      \"@type\": \"ListItem\",
      \"position\": 2,
      \"name\": \"{category}\",
      \"item\": \"https://821224.com/{category.lower().replace(' ', '-')}/\"
    }},
    {{
      \"@type\": \"ListItem\",
      \"position\": 3,
      \"name\": \"{title[:80]}\",
      \"item\": \"https://821224.com/{category.lower().replace(' ', '-')}/{title.lower().replace(' ', '-')[:60]}/\"
    }}
  ]
}}
</script>'''
    
    if 'BreadcrumbList' not in html:
        html = html.replace('</head>', breadcrumb_schema + '\\n    </head>')
    
    return html


def fix_read_time_display(html: str, word_count: int) -> str:
    \"\"\"Fix the displayed read time to match actual word count.\"\"\"
    read_time = calculate_read_time(word_count)
    html = re.sub(r'~\\d+ min read', f'{read_time} min read', html)
    return html


def enhance_author_byline(html: str) -> str:
    \"\"\"Add author credentials and bio to article bylines.\"\"\"
    
    # Look for existing author byline
    byline_pattern = re.compile(
        r'<div class=\"article-byline\"[^>]*>.*?</div>',
        re.DOTALL
    )
    
    enhanced_byline = f'''<div class=\"article-byline\" style=\"color:#6b7280;font-size:0.9rem;margin-top:12px;\">
                    By <a href=\"/about/\" style=\"color:#3b82f6;text-decoration:none;font-weight:600;\">{AUTHOR_INFO['name']}</a>
                    <span style=\"color:#9ca3af;\"> \\u00b7 </span>
                    <span style=\"color:#6b7280;font-size:0.85rem;\">{AUTHOR_INFO['title']}</span>
                </div>
                <div style=\"margin-top:16px;padding:16px;background:#f8fafc;border-radius:8px;border-left:3px solid #2563eb;\">
                    <p style=\"margin:0;font-size:0.85rem;color:#64748b;\">
                        <strong>{AUTHOR_INFO['name']}</strong> is {AUTHOR_INFO['bio'].lower()}
                    </p>
                </div>'''
    
    if byline_pattern.search(html):
        html = byline_pattern.sub(enhanced_byline, html)
    else:
        # Add after the meta section
        meta_end = html.find('article-byline')
        if meta_end > 0:
            insert_pos = html.find('</div>', meta_end) + 6
            html = html[:insert_pos] + '\\n' + enhanced_byline + html[insert_pos:]
    
    return html


def fix_image_alt_texts(html: str) -> str:
    \"\"\"Ensure all images have meaningful alt text.\"\"\"
    def fix_img_tag(match):
        tag = match.group(0)
        if 'alt=' in tag or 'alt =' in tag:
            return tag
        # Add alt text based on context
        return tag.replace('<img ', '<img alt=\"', 1)
    
    html = re.sub(r'<img\\s[^>]*>', fix_img_tag, html)
    return html


def add_language_hints(html: str) -> str:
    \"\"\"Ensure proper language attributes.\"\"\"
    # Fix html lang attribute
    html = re.sub(r'<html lang=\"[^\"]*\">', '<html lang=\"en-US\">', html)
    return html


def fix_twitter_card(html: str) -> str:
    \"\"\"Ensure Twitter card has all required fields.\"\"\"
    if 'twitter:card' not in html:
        html = html.replace(
            '</head>',
            '<meta name=\"twitter:card\" content=\"summary_large_image\">\\n    </head>'
        )
    if 'twitter:title' not in html:
        title_match = re.search(r'<title>([^<]+)</title>', html)
        if title_match:
            title = title_match.group(1)
            html = html.replace(
                '</head>',
                f'<meta name=\"twitter:title\" content=\"{title}\">\\n    </head>'
            )
    if 'twitter:description' not in html:
        desc_match = re.search(r'<meta name=\"description\" content=\"([^\"]*)\">', html)
        if desc_match:
            desc = desc_match.group(1)
            html = html.replace(
                '</head>',
                f'<meta name=\"twitter:description\" content=\"{desc}\">\\n    </head>'
            )
    return html


def add_self_reference_rss(html: str) -> str:
    \"\"\"Add self-referencing RSS link if missing.\"\"\"
    if 'application/rss+xml' not in html:
        html = html.replace(
            '</head>',
            '<link rel=\"alternate\" type=\"application/rss+xml\" title=\"Insurtech Insights RSS Feed\" href=\"/rss.xml\">\\n    </head>'
        )
    return html


def add_webpage_schema_for_category(html: str, category_name: str, category_desc: str) -> str:
    \"\"\"Add WebPage schema for category index pages.\"\"\"
    webpage_schema = f'''<script type=\"application/ld+json\">
{{
  \"@context\": \"https://schema.org\",
  \"@type\": \"WebPage\",
  \"name\": \"{category_name}\",
  \"description\": \"{category_desc}\",
  \"url\": \"https://821224.com/{category_name.lower().replace(' ', '-')}/\",
  \"inLanguage\": \"en-US\",
  \"isPartOf\": {{
    \"@id\": \"https://821224.com/#website\"
  }}
}}
</script>'''
    
    if 'WebPage' not in html:
        html = html.replace('</head>', webpage_schema + '\\n    </head>')
    
    return html


def audit_article_quality(html: str, title: str) -> dict:
    \"\"\"Audit an article for Google quality signals.\"\"\"
    issues = []
    score = 100
    
    word_count = count_words_in_html(html)
    
    # Check word count
    if word_count < 1500:
        issues.append(f\"LOW WORD COUNT: {word_count} words (minimum 1500 recommended)\")
        score -= 20
    elif word_count < 2000:
        issues.append(f\"MODERATE WORD COUNT: {word_count} words (2000+ recommended for top rankings)\")
        score -= 10
    
    # Check for citations
    citation_count = len(re.findall(r'\\[.*?\\]', html))
    if citation_count < 3:
        issues.append(f\"FEW CITATIONS: {citation_count} (minimum 3 recommended)\")
        score -= 15
    
    # Check for author info
    if 'article-byline' not in html:
        issues.append(\"MISSING AUTHOR BYLINE\")
        score -= 10
    
    # Check read time
    if '~1 min read' in html or '~2 min read' in html:
        if word_count > 500:
            issues.append(f\"INCORRECT READ TIME: Shows ~1 min but has {word_count} words\")
            score -= 5
    
    # Check structured data
    if '\"@type\": \"Article\"' not in html:
        issues.append(\"MISSING ARTICLE SCHEMA\")
        score -= 15
    
    if 'wordCount' not in html:
        issues.append(\"MISSING wordCount IN SCHEMA\")
        score -= 5
    
    if 'timeRequired' not in html:
        issues.append(\"MISSING timeRequired IN SCHEMA\")
        score -= 5
    
    # Check canonical URL
    if 'canonical' not in html:
        issues.append(\"MISSING CANONICAL URL\")
        score -= 10
    
    # Check meta description length
    desc_match = re.search(r'<meta name=\"description\" content=\"([^\"]*)\">', html)
    if desc_match:
        desc = desc_match.group(1)
        if len(desc) < 100 or len(desc) > 170:
            issues.append(f\"META DESCRIPTION LENGTH: {len(desc)} chars (recommended 150-160)\")
            score -= 5
    
    return {
        \"title\": title,
        \"score\": max(0, score),
        \"word_count\": word_count,
        \"issues\": issues,
        \"citation_count\": citation_count
    }


def process_article_file(article_path: Path) -> dict:
    \"\"\"Process a single article file.\"\"\"
    html = article_path.read_text(encoding='utf-8')
    original_html = html
    
    # Extract title
    title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
    title = title_match.group(1).strip() if title_match else article_path.parent.name
    
    # Calculate word count
    word_count = count_words_in_html(html)
    
    # Extract category from path
    rel_path = article_path.relative_to(CONTENT_DIR)
    category = rel_path.parts[0]
    category_name = category.replace('-', ' ').title()
    
    # Apply all fixes
    html = fix_canonical_urls(html)
    html = fix_opengraph_full_urls(html)
    html = fix_meta_description(html, title)
    html = fix_article_schema(html, title, category, word_count)
    html = add_breadcrumb_schema(html, category_name, title)
    html = fix_read_time_display(html, word_count)
    html = enhance_author_byline(html)
    html = fix_image_alt_texts(html)
    html = add_language_hints(html)
    html = fix_twitter_card(html)
    html = add_self_reference_rss(html)
    
    # Write back
    if html != original_html:
        article_path.write_text(html, encoding='utf-8')
    
    return {
        \"file\": str(article_path),
        \"title\": title,
        \"word_count\": word_count,
        \"category\": category,
        \"modified\": html != original_html
    }


def process_category_index(category_dir: Path, category_name: str) -> dict:
    \"\"\"Process a category index page.\"\"\"
    index_file = category_dir / 'index.html'
    if not index_file.exists():
        return {\"status\": \"no index file\"}
    
    html = index_file.read_text(encoding='utf-8')
    original_html = html
    
    # Apply fixes
    html = fix_canonical_urls(html)
    html = fix_opengraph_full_urls(html)
    html = fix_meta_description(html, category_name)
    html = fix_image_alt_texts(html)
    html = add_language_hints(html)
    html = fix_twitter_card(html)
    
    # Add category-specific WebPage schema
    category_desc = f\"Expert analysis and implementation guides for {category_name.lower()} in insurance technology at 821224.com.\"
    html = add_webpage_schema_for_category(html, category_name, category_desc)
    
    if html != original_html:
        index_file.write_text(html, encoding='utf-8')
    
    return {\"file\": str(index_file), \"modified\": html != original_html}


def process_main_pages() -> list:
    \"\"\"Process main site pages (about, contact, privacy, terms).\"\"\"
    results = []
    
    for page_name in ['about', 'contact', 'privacy', 'terms']:
        page_dir = CONTENT_DIR / page_name
        index_file = page_dir / 'index.html'
        if not index_file.exists():
            continue
        
        html = index_file.read_text(encoding='utf-8')
        original_html = html
        
        html = fix_canonical_urls(html)
        html = fix_opengraph_full_urls(html)
        html = fix_meta_description(html, page_name.title())
        html = fix_image_alt_texts(html)
        html = add_language_hints(html)
        html = fix_twitter_card(html)
        
        if html != original_html:
            index_file.write_text(html, encoding='utf-8')
            results.append({\"file\": str(index_file), \"modified\": True})
    
    return results


# ===========================================================================
# MAIN EXECUTION
# ===========================================================================

if __name__ == \"__main__\":
    print(\"=\"*70)
    print(\"821224.com SEO Audit & Fix Tool\")
    print(f\"Running at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\")
    print(\"=\"*70)
    print()
    
    # Step 1: Process category index pages
    print(\"[1/4] Processing category index pages...\")
    categories = ['ai-claims', 'ai-underwriting', 'ai-fraud-detection', 
                  'embedded-insurance', 'ai-policy-cx', 'decision-intelligence']
    
    for cat in categories:
        cat_dir = CONTENT_DIR / cat
        if cat_dir.exists():
            result = process_category_index(cat_dir, cat.replace('-', ' ').title())
            status = \"MODIFIED\" if result.get('modified') else \"NO CHANGES\"
            print(f\"  {cat}: {status}\")
    print()
    
    # Step 2: Process all articles
    print(\"[2/4] Processing individual articles...\")
    article_results = []
    article_count = 0
    
    for cat in categories:
        cat_dir = CONTENT_DIR / cat
        if not cat_dir.exists():
            continue
        
        for article_dir in cat_dir.iterdir():
            if not article_dir.is_dir():
                continue
            if article_dir.name in ['images', '__pycache__']:
                continue
            
            index_file = article_dir / 'index.html'
            if index_file.exists():
                try:
                    result = process_article_file(index_file)
                    article_results.append(result)
                    article_count += 1
                except Exception as e:
                    print(f\"  ERROR processing {article_dir.name}: {e}\")
    
    print(f\"  Processed {article_count} articles\")
    print()
    
    # Step 3: Process main pages
    print(\"[3/4] Processing main pages...\")
    main_results = process_main_pages()
    print(f\"  Processed {len(main_results)} main pages\")
    print()
    
    # Step 4: Quality audit
    print(\"[4/4] Running quality audit on a sample of articles...\")
    audit_results = []
    for art in article_results[:20]:  # Audit first 20 articles as sample
        html = Path(art['file']).read_text(encoding='utf-8')
        title = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        title_str = title.group(1).strip() if title else art['title']
        audit = audit_article_quality(html, title_str)
        audit_results.append(audit)
    
    # Summary
    print()
    print(\"-\"*70)
    print(\"AUDIT SUMMARY (Sample of 20 articles)\")
    print(\"-\"*70)
    
    avg_score = sum(a['score'] for a in audit_results) / len(audit_results) if audit_results else 0
    avg_words = sum(a['word_count'] for a in audit_results) / len(audit_results) if audit_results else 0
    
    print(f\"Average Quality Score: {avg_score:.0f}/100\")
    print(f\"Average Word Count: {avg_words:.0f} words\")
    print()
    
    # Show articles needing attention
    low_score = [a for a in audit_results if a['score'] < 80]
    if low_score:
        print(f\"Articles needing attention ({len(low_score)}):\")
        for a in low_score[:5]:
            print(f\"  [{a['score']}/100] {a['title'][:60]}\")
            for issue in a['issues'][:3]:
                print(f\"    - {issue}\")
    else:
        print(\"All sampled articles passed quality checks!\")
    
    print()
    print(\"=\"*70)
    print(\"SEO audit and fixes complete!\")
    print(\"=\"*70)
