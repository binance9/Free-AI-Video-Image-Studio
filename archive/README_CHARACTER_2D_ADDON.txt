AI VIDEO FACTORY - CHARACTER 2D V10.1 CHECKED

- Engine: Lykon/dreamshaper-8
- CUDA: uu tien fp16 variant de giam download/VRAM
- CPU: dung full precision va se cham hon
- Safety checker: GIU NGUYEN
- Auto retry + quality gate xu ly output blank/khong dat
- Setup va RUN tu dong tim cung mot Python
- API version: 1.0.1

Thu tu:
1. SETUP_CHARACTER_2D_LIGHT.bat
2. RUN_CHARACTER_2D_ADDON.bat
3. GET /health -> 1.0.1
4. GET /character-2d/engine
5. POST /character-2d/engine/warmup
6. POST /character-2d/preview


V12 COMPACT GAME PRESET
- Default preset: compact_game
- Square 1024x1024 preview/anchor respects request size instead of forcing 1024x1536.
- Compact/chibi-inspired proportions: shorter body/limbs, slightly larger head, clean silhouette.
- Target character occupancy ~52-82% canvas height with generous margins.
- Hard composition gate rejects oversized/tall/cropped concept-art framing.
- API version 1.2.0. No model redownload required.

V12.3 FROM-REFERENCE
- New POST /character-2d/from-reference accepts an uploaded PNG/JPG/WEBP in Swagger.
- The uploaded image is fit/padded to a square without cropping.
- Img2img always retries from the original reference, preventing progressive drift.
- Prompt only changes explicitly requested attributes; body proportions/framing/silhouette stay reference-led.
- Hard validator + reference similarity gate must pass before reference_result.png is exported.
- Run SETUP_CHARACTER_2D_V12_3_REFERENCE.bat once for upload support; DreamShaper/CLIP are reused.
