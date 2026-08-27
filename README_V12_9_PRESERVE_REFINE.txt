CHARACTER 2D V12.9 — PRESERVE / REFINE MODE

Fixes the remaining from-reference behavior:
- Pure clean/refine requests no longer use diffusion.
- The uploaded reference becomes the source of truth.
- Only gentle sharpening/detail cleanup is applied; colors, pose, proportions and equipment are preserved.
- Unspecified/null attributes are not semantically forced in preserve mode.
- Recolor/edit requests still use the V12.8 material recolor + img2img path.
- Response exposes preserve_mode and diffusion_used for debugging.

Health/API version: 1.2.9

Examples:
Preserve/refine:
  clean and refine the reference character, keep the same design, same female elf identity,
  same bow, same proportions and same colors, improve sharpness and detail, clean light gray background

Recolor/edit:
  keep the same face, body proportions, hairstyle and bow, change the armor colors to burgundy red and gold,
  change the cape to dark red, keep one bow and one quiver
