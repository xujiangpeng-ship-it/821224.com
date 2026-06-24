# Google Quality Guidelines for 821224.com Content

## Critical Requirements (Must Follow)

### 1. E-E-A-T Signals (Experience, Expertise, Authoritativeness, Trustworthiness)

Every article MUST include:
- **Author credibility**: Reference specific industry experience, certifications, or track record
- **Primary data sources**: Cite only VERIFIED sources from the verified_sources list
- **Specific numbers**: Use exact figures with source attribution (e.g., "According to McKinsey's 2024 report...")
- **Implementation details**: Include real-world timelines, costs, and challenges
- **Disclosure**: State any limitations or biases in the analysis

### 2. Content Quality Standards

#### DO:
- Write 1500+ words per article
- Include at least 3 verified citations per article
- Provide actionable insights and implementation guidance
- Use specific examples from real companies
- Include data tables, statistics, and quantitative analysis
- Link to related articles within the site
- Address counterarguments and limitations
- Update dates to reflect current information

#### DON'T:
- Use vague claims without data support
- Repeat the same statistics across multiple articles
- Make unverifiable predictions
- Use marketing language or promotional tone
- Include placeholder text or incomplete sections
- Duplicate content across articles
- Use AI-generated sounding language patterns

### 3. Technical SEO Requirements

#### Meta Tags:
- Title: 50-60 characters, include primary keyword
- Description: 150-160 characters, unique per page
- Keywords: 5-10 relevant terms
- Canonical: Absolute URL to self
- Open Graph: Complete with image, title, description
- Twitter Card: Complete with image and summary

#### Structured Data (JSON-LD):
- Article schema with ALL required fields:
  - headline
  - author (Person type with url)
  - publisher (Organization with logo)
  - datePublished
  - dateModified
  - image
  - wordCount
  - timeRequired
  - articleSection
- BreadcrumbList schema
- WebSite schema (on homepage)
- Organization schema (on all pages)

#### Performance:
- Lazy load images
- Preload critical fonts
- Minimize render-blocking resources
- Use HTTP/2 or HTTP/3

### 4. Citation Policy

Only use citations from the VERIFIED_SOURCES list in citation_check.py.
Each citation must:
1. Be traceable to a real, published source
2. Include the publisher name
3. Include the year of publication
4. Include a working URL when possible
5. Not be paraphrased beyond recognition

### 5. Content Uniqueness

Each article must have:
- Unique angle or perspective
- Different data points cited
- Distinct implementation examples
- Varied structure and approach
- Original analysis and insights

### 6. User Value

Every article should answer:
- What problem does this solve?
- Who is this for?
- What are the specific steps?
- What are the risks and limitations?
- What's the expected ROI or outcome?

## Content Generation Checklist

Before publishing any article, verify:
- [ ] Word count >= 1500
- [ ] At least 3 verified citations
- [ ] Author bio included
- [ ] Read time calculated correctly
- [ ] All meta tags present and unique
- [ ] Structured data complete
- [ ] Internal links to related content
- [ ] No duplicate content with other articles
- [ ] Images have alt text
- [ ] Mobile responsive design
- [ ] Page loads in < 3 seconds
