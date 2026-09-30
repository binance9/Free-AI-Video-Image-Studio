"""Benchmark one fixed ban_do_3d img2img tile without running a whole map."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
from diffusers import AutoPipelineForImage2Image, DPMSolverMultistepScheduler, EulerAncestralDiscreteScheduler
from PIL import Image

from app.modules.ban_do_3d.kiem_tra_ban_do import master_layout_similarity, no_text_heuristic, sharpness


CONFIGS = [
    {"name": "base_512", "resolution": 512, "strength": .58, "steps": 24, "guidance": 7.0, "scheduler": "default"},
    {"name": "dpm_768_s45", "resolution": 768, "strength": .45, "steps": 32, "guidance": 6.5, "scheduler": "dpm"},
    {"name": "dpm_768_s58", "resolution": 768, "strength": .58, "steps": 36, "guidance": 6.5, "scheduler": "dpm"},
    {"name": "euler_768_s62", "resolution": 768, "strength": .62, "steps": 36, "guidance": 7.0, "scheduler": "euler_a"},
    {"name": "dpm_1024_s50", "resolution": 1024, "strength": .50, "steps": 36, "guidance": 6.5, "scheduler": "dpm"},
    {"name": "euler_512_s80", "resolution": 512, "strength": .80, "steps": 48, "guidance": 8.0, "scheduler": "euler_a"},
    {"name": "euler_768_s80", "resolution": 768, "strength": .80, "steps": 48, "guidance": 8.0, "scheduler": "euler_a"},
    {"name": "tiled_2x512_s55", "resolution": 512, "strength": .55, "steps": 32, "guidance": 7.5, "scheduler": "euler_a", "tiled": True},
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--model", default="stable-diffusion-v1-5/stable-diffusion-v1-5")
    parser.add_argument("--cache", type=Path, default=Path("data/models/image"))
    parser.add_argument("--only")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    pipe = AutoPipelineForImage2Image.from_pretrained(
        args.model, torch_dtype=torch.float16, cache_dir=str(args.cache.resolve()), local_files_only=True
    ).to("cuda")
    pipe.enable_attention_slicing("max")
    if hasattr(pipe, "enable_vae_slicing"):
        pipe.enable_vae_slicing()
        pipe.enable_vae_tiling()
    else:
        pipe.vae.enable_slicing()
        pipe.vae.enable_tiling()
    try:
        pipe.enable_xformers_memory_efficient_attention()
    except Exception:
        pass
    original_scheduler = pipe.scheduler.config
    prompt = (
        "Sharp top-down fantasy terrain, broad reference colors. Ground and water only. "
        "No trees, houses or props. No text, labels, icons, UI, borders or frames. "
        "Style: detailed hand-painted game terrain texture, crisp natural ground detail."
    )
    negative = "text, letters, words, label, legend, UI, panel, frame, icon, house, building, tree, prop, blurry, smooth"
    results = []
    for config in CONFIGS:
        if args.only and config["name"] != args.only:
            continue
        size = config["resolution"]
        with Image.open(args.source) as source_image:
            init = source_image.convert("RGB").resize((size, size), Image.Resampling.LANCZOS)
        if config["scheduler"] == "dpm":
            pipe.scheduler = DPMSolverMultistepScheduler.from_config(original_scheduler, algorithm_type="dpmsolver++", use_karras_sigmas=True)
        elif config["scheduler"] == "euler_a":
            pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(original_scheduler)
        else:
            pipe.scheduler = pipe.scheduler.__class__.from_config(original_scheduler)
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        started = time.perf_counter()
        try:
            if config.get("tiled"):
                with Image.open(args.source) as source_image:
                    source_image=source_image.convert("RGB").resize((512,512),Image.Resampling.LANCZOS)
                image=Image.new("RGB",(1024,1024))
                for row in range(2):
                    for col in range(2):
                        patch=source_image.crop((col*256,row*256,(col+1)*256,(row+1)*256)).resize((512,512),Image.Resampling.LANCZOS)
                        generator=torch.Generator(device="cuda").manual_seed(1136925195+row*2+col)
                        refined=pipe(
                            prompt=prompt+" Fine ground microtexture, crisp erosion detail, detailed soil and stone surface.",
                            negative_prompt=negative,
                            image=patch,
                            strength=config["strength"],num_inference_steps=config["steps"],
                            guidance_scale=config["guidance"],generator=generator,
                        ).images[0]
                        image.paste(refined,(col*512,row*512))
            else:
                generator = torch.Generator(device="cuda").manual_seed(1136925195)
                image = pipe(
                    prompt=prompt,
                    negative_prompt=negative,
                    image=init,
                    strength=config["strength"],
                    num_inference_steps=config["steps"],
                    guidance_scale=config["guidance"],
                    generator=generator,
                ).images[0]
            output = args.output / f"{config['name']}.png"
            image.save(output)
            row = {
                **config,
                "seconds": round(time.perf_counter() - started, 2),
                "peak_vram_mib": round(torch.cuda.max_memory_allocated() / 1024**2),
                "sharpness": sharpness(output),
                "layout": master_layout_similarity(output, args.source),
                "no_text": no_text_heuristic(output),
                "output": str(output),
            }
        except torch.OutOfMemoryError as exc:
            row = {**config, "error": "CUDA OOM", "seconds": round(time.perf_counter() - started, 2)}
            torch.cuda.empty_cache()
        results.append(row)
        (args.output / "benchmark.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()
