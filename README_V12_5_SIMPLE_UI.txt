CHARACTER 2D V12.5 SIMPLE UI

New compact workflow:
- Open http://127.0.0.1:8012/character-2d/ui
- Choose reference image
- Enter prompt
- Keep preset compact_game
- Adjust strength only if needed
- Click Generate

Advanced options are collapsed by default.
The old long /character-2d/from-reference form is hidden from Swagger.
Swagger exposes /character-2d/from-reference-simple with only:
- image
- prompt
- preset
- strength

V12.4 output guard is included:
- black/blank/transparent output rejection
- light gray flattening for accepted exports
- retry repair hints

Version: 1.2.5
