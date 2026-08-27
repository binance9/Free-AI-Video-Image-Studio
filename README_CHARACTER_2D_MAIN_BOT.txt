AI VIDEO FACTORY 0.8.9.1 - CHARACTER 2D MAIN BOT INTEGRATION

What this patch does
- Adds a separate professional Character 2D module to the main bot.
- Character 2D is NOT mixed into the old AI Image module.
- Adds a new colorful "NHAN VAT & GAME ASSET" section on Home.
- Adds Character 2D and Character 3D cards with separate visual identities.
- Character 2D simple flow: optional reference image -> prompt -> Generate -> PASS/REJECT.
- Recolor/preserve/edit modes are auto-detected.
- High-confidence recolor gate is connected to final export.
- PASS output has a "DUNG ANH NAY TAO 3D" handoff button.
- The handoff pushes the 2D PNG directly into the existing AI 3D Studio image input.

Versions
- Main bot UI: 0.8.9.1
- Character 2D: 1.3.2

Install
1. Stop AI Video Factory.
2. Extract this ZIP directly into the ai_video_factory project root.
3. Allow Replace for matching files.
4. Start the main bot normally on port 8123.
5. Home -> NHAN VAT & GAME ASSET -> Nhan vat 2D.

Quick check
- GET /api/character-2d/status should return version 1.3.2.
- Home should show a new colorful 2D/3D game-asset section.
- After Character 2D PASS, click "DUNG ANH NAY TAO 3D"; AI 3D Studio should open with that image already selected.
