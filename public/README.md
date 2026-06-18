# Static Images Directory

This directory contains website static assets including images.

## Required Images

Please add the following images to this directory:

1. **insurtech-insight-og.jpg** - Open Graph image for social sharing (recommended size: 1200x630 pixels)
2. **logo-main.png** - Main website logo (recommended size: 200x60 pixels)

## Image Guidelines

- Open Graph image should be:
  - Size: 1200x630 pixels (2:1 ratio)
  - Format: JPG or PNG
  - Include your website name and branding
  - Keep text minimal and readable

- Logo should be:
  - Size: Around 200x60 pixels
  - Format: PNG with transparency
  - Light background compatible (white or transparent background)
  - High resolution for retina displays

## Why These Images Are Needed

These images are referenced in your Hugo configuration (hugo.toml):
```toml
[params]
  images = ["/images/insurtech-insight-og.jpg"]
  logo = "/images/logo-main.png"
```

They are used for:
- Social media sharing (Open Graph tags)
- SEO meta tags
- Website branding elements
