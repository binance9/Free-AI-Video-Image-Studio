CHARACTER 2D V13.1 IDENTITY FALLBACK

Fixes:
- CLIP identity scorer errors no longer become identity=0%.
- Adds a color-insensitive grayscale/edge structural fallback for reference identity.
- Recolor jobs may change palette without losing identity score.
- "create ... based on reference" with no actual requested transformation routes to preserve-refine instead of unnecessary diffusion.

Expected /health version: 1.3.1
