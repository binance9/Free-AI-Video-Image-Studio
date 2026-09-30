"""Generate character images locally using SDXL on GPU.
No third-party API — pure local diffusion on RTX 5060 Ti.
"""
import sys
import time
from pathlib import Path

# Ensure project root is importable
PROJECT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT))

import torch
from diffusers import AutoPipelineForText2Image

OUTPUT_DIR = PROJECT / "generated_characters"
OUTPUT_DIR.mkdir(exist_ok=True)

MODEL_ID = "stabilityai/stable-diffusion-xl-base-1.0"
CACHE_DIR = Path.home() / ".cache" / "huggingface"

def generate(prompt: str, filename: str, style_negative: str = "", steps: int = 20):
    """Generate one image with SDXL."""
    print(f"\n{'='*60}")
    print(f"Generating: {filename}")
    print(f"Prompt: {prompt[:120]}...")
    print(f"Steps: {steps}")
    print(f"{'='*60}")

    pipe = AutoPipelineForText2Image.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16,
        variant="fp16",
        cache_dir=str(CACHE_DIR),
    ).to("cuda")

    # Use 1024x1024 for SDXL
    generator = torch.Generator(device="cuda").manual_seed(42)

    start = time.perf_counter()

    image = pipe(
        prompt=prompt,
        negative_prompt=style_negative,
        width=1024,
        height=1024,
        num_inference_steps=steps,
        guidance_scale=7.0,
        generator=generator,
    ).images[0].convert("RGB")

    elapsed = time.perf_counter() - start
    print(f"Generation time: {elapsed:.1f}s")

    out_path = OUTPUT_DIR / filename
    image.save(str(out_path), "PNG", optimize=True)
    print(f"Saved: {out_path}")
    print(f"VRAM peak: {torch.cuda.max_memory_allocated()/1024**3:.2f} GB")

    # Cleanup
    del pipe
    gc = __import__("gc")
    gc.collect()
    torch.cuda.empty_cache()

    return out_path


if __name__ == "__main__":
    # Character 1: 2D Anime style elf archer
    prompt_2d = (
        "1girl, solo, female elf archer, long golden hair, green eyes, pointed elf ears, "
        "holding ornate magical bow, glowing green energy bow, fantasy leather armor with leaf patterns, "
        "standing in enchanted forest, anime style, cel shaded, clean lineart, vibrant colors, "
        "detailed anime illustration, full body, professional character design, masterpiece, best quality"
    )
    neg_2d = (
        "3d render, photorealistic, cgi, chibi, deformed, bad anatomy, extra limbs, "
        "bad hands, blurry, low quality, multiple people, character sheet, lineup"
    )

    # Character 2: 3D Render style elf archer
    prompt_3d = (
        "1girl, solo, female elf archer, long golden hair, green eyes, pointed elf ears, "
        "holding ornate magical bow, glowing green energy bow, fantasy leather armor with leaf patterns, "
        "standing in enchanted forest, 3D render, Unreal Engine 5 quality, cinematic volumetric lighting, "
        "soft shadows, highly detailed, realistic textures, fantasy game character, full body, masterpiece"
    )
    neg_3d = (
        "anime, 2d, flat shading, cartoon, chibi, deformed, bad anatomy, extra limbs, "
        "bad hands, blurry, low quality, multiple people, character sheet, lineup"
    )

    print("Loading SDXL model (first run will download ~7GB)...")
    t0 = time.perf_counter()

    img1 = generate(prompt_2d, "character_2d_elf_archer.png", neg_2d, steps=20)
    img2 = generate(prompt_3d, "character_3d_elf_archer.png", neg_3d, steps=20)

    total = time.perf_counter() - t0
    print(f"\n{'='*60}")
    print(f"DONE! Total time: {total:.1f}s")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"  2D: {img1}")
    print(f"  3D: {img2}")
