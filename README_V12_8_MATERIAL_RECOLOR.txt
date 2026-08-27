CHARACTER 2D V12.8 — MATERIAL RECOLOR

Fixes the case where from-reference keeps the old green palette even though the prompt requests burgundy red / gold / dark red.

What changed:
- Recolor requests now get a deterministic material-color pass before img2img.
- Geometry, face, pose and weapon shape remain from the reference.
- Existing gold trim is preserved while the dominant garment/cape material is moved to the requested primary color.
- Img2img only performs a light refinement after the palette transfer instead of trying to invent the recolor itself.
- Response includes recolor_prefill diagnostics.
- API version: 1.2.8

No model re-download is required.
