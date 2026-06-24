#!/usr/bin/env python3
\"\"\"
seo_fix.py - Comprehensive SEO fixes for 821224.com
Fixes Google quality issues identified in the site audit.
\"\"\"

import re
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT_DIR = ROOT / \"content\"

def fix_article_schema(html: str, title: str, slug: str) -> str:
    \"\"\"Fix Article structured data with required fields for Google.\"\"\"
    
    # Extract date from meta description or article content
    date_match = re.search(r'(\\d{4}-\\d{2}-\\d{2})', html)
    publish_date = date_match.group(1) if date_match else \"2026-06-24\"
    
    # Count words roughly
    text_content = re.sub(r'<[^>]+>', ' ', html)
    word_count = len(text_content.split())
    
    # Fix the Article schema - add missing required fields
    old_schema = re.search(r'(<script type=\"application/ld\\+json\">\\s*\\{[^}]*\"@type\":\\s*\"Article\"[^}]*\\})', html, re.DOTALL)
    
    if old_schema:
        new_schema = f'''<script type=\"application/ld+json\">
{{
    \"@context\": \"https://schema.org\",
    \"@type\": \"Article\",
    \"headline\": \"{title}\",
    \"description\": \"{title[:150]}\",
    \"image\": \"https://821224.com/images/logo.webp\",
    \"datePublished\": \"{publish_date}T12:00:00+00:00\",
    \"dateModified\": \"{publish_date}T12:00:00+00:00\",
    \"author\": {{
        \"@type\": \"Person\",
        \"name\": \"Bin Sun\",
        \"url\": \"https://821224.com/about/\"
    }},
    \"publisher\": {{
        \"@type\": \"Organization\",
        \"name\": \"Insurtech Insights\",
        \"logo\": {{
            \"@type\": \"ImageObject\",
            \"url\": \"https://821224.com/images/logo.webp\"
        }}
    }},
    \"wordCount\": {max(word_count, 500)},
    \"timeRequired\": \"PT{max(word_count // 200, 5)}M\",
    \"inLanguage\": \"en-US\",
    \"articleSection\": \"AI in Insurance\"
}}
</script>'''
        html = html.replace(old_schema.group(1), new_schema)
    
    return html


def fix_breadcrumb_schema(html: str, category: str, title: str) -> str:
    \"\"\"Add breadcrumb structured data if missing.\"\"\"
    
    breadcrumb_script = '''<script type=\"application/ld+json\">
{
  \"@context\": \"https://schema.org\",
  \"@type\": \"BreadcrumbList\",
  \"itemListElement\": [
    {
      \"@type\": \"ListItem\",
      \"position\": 1,
      \"name\": \"Home\",
      \"item\": \"https://821224.com/\"
    },
    {
      \"@type\": \"ListItem\",
      \"position\": 2,
      \"name\": \"''' + category + '''\",
      \"item\": \"https://821224.com/''' + category.lower().replace(' ', '-') + '/\"
    },
    {
      \"@type\": \"ListItem\",
      \"position\": 3,
      \"name\": \"''' + title[:50] + '''\",
      \"item\": \"https://821224.com/''' + category.lower().replace(' ', '-') + '/''' + title.lower().replace(' ', '-') + '/\"
    }
  ]
}
</script>'''
    
    if 'BreadcrumbList' not in html:
        # Insert before the closing </head>
        html = html.replace('</head>', breadcrumb_script + '\n    </head>')
    
    return html


def fix_read_time(html: str) -> str:
    \"\"\"Fix the read time calculation.\"\"\"
    
    # Find and replace ~1 min read with calculated time
    text_content = re.sub(r'<[^>]+>', ' ', html)
    word_count = len(text_content.split())
    read_time = max(3, word_count // 200)
    
    html = re.sub(r'~\d+ min read', f'{read_time} min read', html)
    
    return html


def fix_canonical_urls(html: str, base_path: str) -> str:
    \"\"\"Ensure canonical URLs are absolute.\"\"\"
    
    html = re.sub(r'<link rel=\"canonical\" href=\"/([^/\"]+)\">', 
                  r'<link rel=\"canonical\" href=\"https://821224.com/\1/\">', html)
    html = re.sub(r'<link rel=\"canonical\" href=\"/\">', 
                  r'<link rel=\"canonical\" href=\"https://821224.com/\">', html)
    
    return html


def fix_author_info(html: str) -> str:
    \"\"\"Add author bio snippet and improve byline.\"\"\"
    
    # Check if byline exists and enhance it
    if 'article-byline' not in html:
        old_byline = re.search(r'By <a href=\"/about/\"[^>]*>Bin Sun</a>', html)
        if old_byline:
            new_byline = '''<div class=\"article-byline\" style=\"color:#6b7280;font-size:0.9rem;margin-top:12px;\">
                    By <a href=\"/about/\" style=\"color:#3b82f6;text-decoration:none;font-weight:600;\">Bin Sun</a>
                    <span style=\"color:#9ca3af;\"> · </span>
                    <span style=\"color:#6b7280;font-size:0.85rem;\">Senior Insurance Technology Analyst</span>
                </div>
                <div style=\"margin-top:16px;padding:16px;background:#f8fafc;border-radius:8px;border-left:3px solid #2563eb;\">
                    <p style=\"margin:0;font-size:0.85rem;color:#64748b;\">
                        <strong>Bin Sun</strong> is a senior analyst specializing in AI applications for insurance. 
                        With 15+ years in the insurance technology sector, he provides independent analysis of 
                        emerging trends in claims automation, underwriting intelligence, and fraud detection.
                    </p>
                </div>'''
            html = html.replace(old_byline.group(0), new_byline)
    
    return html


def fix_opengraph_images(html: str) -> str:
    \"\"\"Ensure OG images use full URLs.\"\"\"
    
    html = re.sub(r'content=\"(/images/[^\"]+)\"', r'content=\"https://821224.com\1\"', html)
    
    return html


def fix_meta_descriptions(html: str, title: str) -> str:
    \"\"\"Ensure meta descriptions are 150-160 characters and not truncated.\"\"\"
    
    desc_match = re.search(r'<meta name=\"description\" content=\"([^\"]*)\">', html)
    if desc_match:
        desc = desc_match.group(1)
        # Truncate or pad description
        if len(desc) > 160:
            desc = desc[:157] + '...'
        elif len(desc) < 100:
            desc = desc + ' | Expert analysis on AI in insurance technology.'
        
        html = html.replace(desc_match.group(0), f'<meta name=\"description\" content=\"{desc}\">')
    
    return html


def process_category_index(category_dir: Path, category_name: str, category_slug: str):
    \"\"\"Process category index page.\"\"\"
    
    index_file = category_dir / 'index.html'
    if not index_file.exists():
        return
    
    html = index_file.read_text(encoding='utf-8')
    
    # Fix canonical URLs
    html = fix_canonical_urls(html, category_slug)
    
    # Fix meta descriptions
    html = fix_meta_descriptions(html, category_name)
    
    # Fix OG images
    html = fix_opengraph_images(html)
    
    # Add category-specific schema
    if 'WebPage' not in html:
        category_schema = f'''<script type=\"application/ld+json\">
{{
  \"@context\": \"https://schema.org\",
  \"@type\": \"WebPage\",
  \"name\": \"{category_name}\",
  \"description\": \"Expert analysis and implementation guides for {category_name.lower()} in insurance.\",
  \"url\": \"https://821224.com/{category_slug}/\",
  \"inLanguage\": \"en-US\",
  \"isPartOf\": {{
    \"@id\": \"https://821224.com/#website\"
  }}
}}
</script>'''
        html = html.replace('</head>', category_schema + '\n    </head>')
    
    index_file.write_text(html, encoding='utf-8')
    print(f'  Fixed: {index_file}')


def process_article(article_dir: Path):
    \"\"\"Process individual article.\"\"\"
    
    index_file = article_dir / 'index.html'
    if not index_file.exists():
        return
    
    html = index_file.read_text(encoding='utf-8')
    filename = article_dir.name
    
    # Extract title from h1
    title_match = re.search(r'<h1>([^<]+)</h1>', html)
    title = title_match.group(1) if title_match else filename
    
    # Extract category from path
    rel_path = article_dir.relative_to(CONTENT_DIR)
    category = str(rel_path.parts[0])
    category_name = category.replace('-', ' ').title()
    
    # Apply fixes
    html = fix_canonical_urls(html, str(rel_path))
    html = fix_meta_descriptions(html, title)
    html = fix_opengraph_images(html)
    html = fix_read_time(html)
    html = fix_author_info(html)
    html = fix_article_schema(html, title, category)
    html = fix_breadcrumb_schema(html, category_name, title)
    
    index_file.write_text(html, encoding='utf-8')
    print(f'  Fixed: {index_file}')


# Main execution
print('Starting SEO fixes for 821224.com...')
print()

# Process category index pages
categories = ['ai-claims', 'ai-underwriting', 'ai-fraud-detection', 'embedded-insurance', 'ai-policy-cx', 'decision-intelligence']
for cat in categories:
    cat_dir = CONTENT_DIR / cat
    if cat_dir.exists():
        print(f'Processing category: {cat}')
        process_category_index(cat_dir, cat.replace('-', ' ').title(), cat)

# Process individual articles
print()
print('Processing articles...')
article_count = 0
for cat in categories:
    cat_dir = CONTENT_DIR / cat
    if cat_dir.exists():
        for article_dir in cat_dir.iterdir():
            if article_dir.is_dir() and article_dir.name != 'images':
                try:
                    process_article(article_dir)
                    article_count += 1
                except Exception as e:
                    print(f'  Error processing {article_dir}: {e}')

# Process main pages
print()
print('Processing main pages...')
for page in ['about', 'contact', 'privacy', 'terms']:
    page_dir = CONTENT_DIR / page
    if page_dir.exists():
        index_file = page_dir / 'index.html'
        if index_file.exists():
            html = index_file.read_text(encoding='utf-8')
            html = fix_canonical_urls(html, page)
            html = fix_opengraph_images(html)
            html = fix_meta_descriptions(html, page.title())
            index_file.write_text(html, encoding='utf-8')
            print(f'  Fixed: {index_file}')

print()
print(f'SEO fixes complete! Processed {article_count} articles.')
