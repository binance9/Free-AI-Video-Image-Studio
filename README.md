# AI Video Factory — Free All-In-One Local AI Studio

```
================================================================
   AI VIDEO FACTORY v0.8.9
   FREE · LOCAL · NO API COSTS · RUNS 100% ON YOUR PC
   Video - Image - 3D - Subtitles - Music - Download - Edit
================================================================
```

**AI Video Factory** is a free, open-source, all-in-one AI studio that runs **entirely on your own computer**. No subscriptions, no per-video payments, no cloud uploads — your GPU does all the work. Create videos from a text idea, generate and edit images, build 3D characters, clean up footage, add subtitles and music, download videos, and export the final MP4 — all in one Windows app with a CapCut-style editor.

Everything is in a Vietnamese-first UI, with open English AI models under the hood.

## What's inside

### VIDEO
- **AI Video Director** — type an idea ("30s video about an archer entering an ancient castle, wuxia style") and it auto-builds: script → storyboard → scene images → motion → voice → subtitles → music → final MP4. One button.
- **FramePack engine** — long AI video (up to 60s) from a single image, or from a Vietnamese script with no image at all (auto-translates + auto-draws the first frame). 100% local, free forever.
- **Wan 2.2 video engine** — local text-to-video and image-to-video at 720p.
- **Video editor** — cut, merge, text/image overlays, timeline editing (CapCut-style).
- **AI video cleanup** — remove background, erase text/logos/objects from videos with inpainting.
- **Video download** — pull public Facebook videos (and other sites via yt-dlp) straight into the editor.

### IMAGE
- **AI image generation** — text-to-image, image-to-image, inpainting and upscaling with local Stable Diffusion (SDXL / SD 1.5 / DreamShaper). 7 styles: photo, cinematic, anime, cartoon3d, illustration, product, fantasy.
- **AI image editing** inside the editor (masks, reference-based edits).

### 3D
- **2D character creation** — character sheets with consistency gates (face lock, body lock, weapon check).
- **3D characters from a photo** — three interchangeable backends (TripoSR / Hunyuan3D-2 / Character-HD), textured GLB export.
- **Game-ready pipeline** — Blender scripting: optimize → rig → skin → idle/run/attack animations → export.
- **3D props** — 13 categories with poly/texture budget control.
- **HD map generator** — AI tile-map generator: layout lock, per-tile generation, overlap stitching, sharpness QA.

### AUDIO / TEXT
- **Subtitles** — local Whisper transcription + Argos Translate translation.
- **Music** — local music library, smart clip selector, mixer.
- **Text presets** — ready-made caption styles.
- **Voice assistant** — optional wake-word assistant ("gà ơi dậy đi") with Vietnamese speech.

## Requirements

- Windows 10/11, NVIDIA GPU (8 GB VRAM minimum, 16 GB recommended)
- ~50 GB free disk for AI models (downloaded once, cached locally)
- Python 3.14, FFmpeg, Blender (only for the game-ready 3D pipeline)

## Quick start

```bat
git clone https://github.com/binance9/Free-AI-Video-Image-Studio.git
cd Free-AI-Video-Image-Studio
pip install -r requirements.txt
START_VIDEO_FACTORY.bat
```

Then open the app, pick a tool card on the home screen, and go. First use of each AI tool downloads its model once.

## Project layout

```
app/modules/*   feature modules (video, image, 3d, subtitles, music...)
web/            frontend (home + editor + per-module panels)
tools/          installers and helpers
tests/smoke/    fast smoke tests: pytest -q tests/smoke/
data/           runtime data & model cache (created locally, not in git)
```

See `DANH_SACH_MODULE.md` (Vietnamese) for the full module index with per-module APIs, tests and troubleshooting.

## License

MIT — free for personal and commercial use. Bundled AI models keep their own licenses (Apache-2.0 for Wan/FramePack/Hunyuan, OpenRAIL for Stable Diffusion).

## Credits

Built as a personal local-AI factory. Video engine: [FramePack](https://github.com/lllyasviel/FramePack) by lllyasviel, Wan 2.2 by Alibaba, HunyuanVideo by Tencent, Whisper by OpenAI. This project just wires them into one friendly studio.
