# Relax Skarpety — Website

Landing page for **Relax Skarpety**, a sock and tights manufacturer based in Tomaszów Lubelski, Poland. In business since 1992. This is my first real client-style project.

**Live:** https://pantoyt.github.io/Relax-Skarpety/

## Features

- Auto-playing product image carousel with infinite scroll
- Pause on hover, manual prev/next controls
- Click-to-copy email address in contact strip
- Google Maps embed
- Social links (Facebook, Instagram)
- Responsive — full desktop layout + mobile fallback
- Fade-in animations on scroll (IntersectionObserver)

## Stack

Pure HTML / CSS / JavaScript. No frameworks, no dependencies.

| Asset | Source |
|---|---|
| `Brush 445` | Local font (`fonts/` directory) — main display font |
| `Cormorant Garamond + DM Sans` | Google Fonts |

## File Structure

```
Relax-Skarpety/
├── index.html
├── fonts/
│   ├── brush-445.woff2
│   └── brush-445.woff
├── images/
│   ├── img1.jpg – img10.jpg   ← carousel product photos
│   └── skarpetki-bg.jpg       ← mobile section background
└── icons/
    ├── favicon.png
    ├── facebook.svg
    └── instagram.svg
```

## What can be removed

The following files from the original version are no longer used and can be deleted:

- Any PNG social icons (replaced by SVG)
- `images/thumbnails/` folder if present

## Notes

- Static site — no server, no CMS, no database
- Deploys to any static host (GitHub Pages, Netlify, etc.)
- No build step required