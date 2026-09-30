# AI Video Factory — Free All-In-One Local AI Studio

```
================================================================
    AI VIDEO FACTORY  ·  v0.8.9
    FREE  ·  LOCAL  ·  NO API COSTS  ·  RUNS 100% ON YOUR PC
    Video | Image | 3D | Subtitles | Music | Download | Edit
================================================================
```

**AI Video Factory** is a free, open-source, all-in-one AI studio that runs **entirely on your own computer**.
No subscriptions. No per-video payments. No cloud uploads. Your GPU does all the work.

Type a text idea → get a finished MP4. Generate and edit images. Build 3D characters.
Clean up footage. Add subtitles and music. Download videos. All in one Windows app
with a CapCut-style timeline editor.

> UI is Vietnamese-first. All AI models are open-source and run locally.

---

## Table of contents

1. [What's inside](#whats-inside)
2. [Requirements](#requirements--read-before-downloading)
3. [How to download and install](#how-to-download-and-install-step-by-step)
4. [Project layout](#project-layout)
5. [License](#license)
6. [Credits](#credits)

---

## What's inside

### 1. VIDEO — create, edit, clean, download

| Tool | What it does |
|---|---|
| **AI Video Director** | Type an idea (e.g. *"30s video about an archer entering an ancient castle, wuxia style"*) → it auto-builds script → storyboard → scene images → motion → voice → subtitles → music → final MP4. One button. |
| **FramePack engine** | Long AI video (up to 60 s) from a **single image**, or from a **plain Vietnamese script with no image at all** (auto-translates + auto-draws the first frame). |
| **Wan 2.2 engine** | Local text-to-video and image-to-video at 720p. |
| **Video editor** | Cut, merge, text/image overlays, CapCut-style timeline. |
| **AI video cleanup** | Remove background; erase text, logos and objects with inpainting. |
| **Video downloader** | Pull public Facebook videos (and other sites via yt-dlp) straight into the editor. |

### 2. IMAGE — generate and edit

| Tool | What it does |
|---|---|
| **AI image generation** | Text-to-image, image-to-image, inpainting, upscaling. Local Stable Diffusion (SDXL / SD 1.5 / DreamShaper). 7 styles: photo, cinematic, anime, cartoon3d, illustration, product, fantasy. |
| **AI image editing** | Mask-based edits and reference-based edits inside the editor. |

### 3. 3D — characters, props, maps

| Tool | What it does |
|---|---|
| **2D character creation** | Character sheets with consistency gates (face lock, body lock, weapon check). |
| **3D characters from a photo** | Three interchangeable backends (TripoSR / Hunyuan3D-2 / Character-HD). Textured GLB export. |
| **Game-ready pipeline** | Blender scripting: optimize → rig → skin → idle/run/attack animations → export. |
| **3D props** | 13 categories with polygon/texture budget control. |
| **HD map generator** | AI tile-map generator: layout lock, per-tile generation, overlap stitching, sharpness QA. |

### 4. AUDIO / TEXT

| Tool | What it does |
|---|---|
| **Subtitles** | Local Whisper transcription + Argos Translate translation. |
| **Music** | Local music library, smart clip selector, mixer. |
| **Text presets** | Ready-made caption styles. |
| **Voice assistant** | Optional Vietnamese wake-word assistant. |

---

## REQUIREMENTS — read before downloading

| Item | Minimum | Recommended |
|---|---|---|
| OS | Windows 10 64-bit | Windows 11 64-bit |
| GPU | NVIDIA, 8 GB VRAM | NVIDIA RTX, 16 GB VRAM |
| RAM | 16 GB | 32 GB or more |
| Free disk | 10 GB (editor only) | 60+ GB (all AI models) |
| Software | Python 3.14, FFmpeg | + Git, + Blender (for 3D game-ready) |

**Important notes**

- An **NVIDIA GPU is required** for all AI generation. No NVIDIA card = editor-only mode.
- AI models download automatically on first use of each tool, then are cached forever (full set ≈ 50 GB).
- Nothing leaves your machine. Internet is only needed for first model download and video downloads.
- Slower GPUs still work — video generation just takes longer (minutes per second of video on 16 GB cards).

## HOW TO DOWNLOAD AND INSTALL (step by step)

**Step 1 — Install Git for Windows**
Download from <https://git-scm.com/download/win> and click Next through the installer.

**Step 2 — Install Python 3.14**
Download from <https://www.python.org/downloads/>.
IMPORTANT: on the first installer screen, tick **"Add python.exe to PATH"**.

**Step 3 — Install FFmpeg**
Download from <https://www.gyan.dev/ffmpeg/builds/>, unzip, and add its `bin` folder to PATH
(search Windows for "environment variables" → Edit → Path → New).

**Step 4 — Download this project**
Open PowerShell or CMD and run:

```bat
git clone https://github.com/binance9/Free-AI-Video-Image-Studio.git
cd Free-AI-Video-Image-Studio
pip install -r requirements.txt
```

**Step 5 — Run**

```bat
START_VIDEO_FACTORY.bat
```

The app opens at `http://127.0.0.1:8000`. Pick any tool card on the home screen and start.
First use of each AI tool downloads its model once — be patient, it only happens once.

*(Optional sanity check: `pytest -q tests/smoke/` — every test runs in seconds.)*

---

## Project layout

```
app/modules/*   feature modules (video, image, 3d, subtitles, music...)
web/            frontend (home screen + editor + per-module panels)
tools/          installers and helpers
tests/smoke/    fast smoke tests
data/           runtime data & model cache — created on your machine, not in git
archive/        development history (old build notes, installers, test reports)
docs/           project docs (module index, architecture, maintenance)
```

Full module index (APIs, tests, troubleshooting per module): see [`docs/DANH_SACH_MODULE.md`](docs/DANH_SACH_MODULE.md) (Vietnamese).

---

## License

MIT — free for personal and commercial use.
Bundled AI models keep their own licenses (Apache-2.0 for Wan / FramePack / Hunyuan, OpenRAIL for Stable Diffusion).

## Credits

Built as a personal local-AI factory. Engines wired together by this project:

- [FramePack](https://github.com/lllyasviel/FramePack) by lllyasviel — long video from one image
- Wan 2.2 by Alibaba — text/image to video
- HunyuanVideo / Hunyuan3D-2 by Tencent
- Whisper by OpenAI — subtitles
- Stable Diffusion by Stability AI

This project just wires them into one friendly studio.
