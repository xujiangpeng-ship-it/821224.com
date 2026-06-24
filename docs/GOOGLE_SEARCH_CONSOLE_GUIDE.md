# Google Search Console Submission Guide for 821224.com

## Step 1: Verify Site Ownership

### Option A: HTML File Upload (Recommended)
1. Create a file named googleXXXXXXXXXXXX.html with the verification code from Google
2. Place it in the public/ directory of your Hugo site
3. Upload to Cloudflare Pages

### Option B: DNS Record
1. Add a TXT record to your Cloudflare DNS:
   - Name: @
   - Value: google-site-verification=XXXXXXXXXXXX
   - TTL: Auto

### Option C: HTML Tag
1. Add this meta tag to your site's <head>:
   <meta name="google-site-verification" content="XXXXXXXXXXXX" />

## Step 2: Submit Sitemap

1. Go to Google Search Console: https://search.google.com/search-console
2. Add property: https://821224.com
3. Navigate to Sitemaps
4. Submit: https://821224.com/sitemap.xml

## Step 3: Request Indexing

After submitting the sitemap:
1. Use the URL Inspection tool for key pages
2. Click "Request Indexing" for:
   - Homepage: https://821224.com/
   - Category pages (6 categories)
   - Top 10 most important articles

## Step 4: Monitor Core Web Vitals

Check regularly at: https://search.google.com/search-console/core-web-vitals
Key metrics to monitor:
- LCP (Largest Contentful Paint): < 2.5s
- FID (First Input Delay): < 100ms
- CLS (Cumulative Layout Shift): < 0.1

## Step 5: Monitor Coverage Issues

Check at: https://search.google.com/search-console/coverage
Address any:
- Errors (pages that can't be indexed)
- Valid warnings (pages with issues but still indexed)
- Excluded pages (intentionally not indexed)

## Step 6: Track Performance

Monitor at: https://search.google.com/search-console/performance
Key metrics:
- Average position (target: improve over time)
- Clicks (target: increase over time)
- Impressions (target: increase over time)
- CTR (target: > 3% for informational queries)

## Step 7: Address Manual Actions

If Google has issued a manual action:
1. Check: https://search.google.com/search-console/manual-actions
2. Read the violation notice carefully
3. Fix ALL content quality issues
4. Submit a reconsideration request

## Ongoing Maintenance

### Weekly:
- Review Search Console for new errors
- Check for significant traffic drops

### Monthly:
- Audit top 20 pages for content quality
- Verify all structured data is valid
- Check Core Web Vitals scores
- Review crawl errors

### Quarterly:
- Full content quality audit
- Update stale content
- Add new high-quality articles
- Review and update schema markup
