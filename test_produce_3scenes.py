"""Submit a 3-scene produce request to the running AI Video Factory server."""
import json
import urllib.request
import time
import sys

HOST = "127.0.0.1"
PORT = 8124
BASE = f"http://{HOST}:{PORT}"

# Step 1: Create plan
plan_req = json.dumps({
    "idea": "Một cô gái cung thủ elf với tóc bạc, mặc áo giáp da, cầm cung dài, đang đứng trước cổng thành cổ. Scene 1: đứng vững vàng nhìn về phía trước, tay cầm cung. Scene 2: bước đi chậm rãi qua cổng thành, tóc bay trong gió. Scene 3: quay đầu nhìn lại, ánh mắt quyết tâm",
    "duration_seconds": 9,
    "platform": "TikTok/Reels",
    "aspect_ratio": "9:16",
    "style": "cinematic, polished, modern fantasy",
    "audience": "người xem phổ thông",
    "goal": "thu hút người xem và truyền tải ý chính rõ ràng",
    "voice_style": "tự nhiên, rõ, có nhịp",
    "music_mood": "cinematic fantasy phù hợp nội dung",
    "captions": True,
    "character_lock": True,
    "quality_priority": "quality_first"
}).encode("utf-8")

req = urllib.request.Request(
    f"{BASE}/api/ai-video-director/plan",
    data=plan_req,
    headers={"Content-Type": "application/json"},
    method="POST"
)
with urllib.request.urlopen(req, timeout=120) as resp:
    plan_data = json.loads(resp.read().decode("utf-8"))

plan = plan_data["plan"]
print(f"Plan created: {plan.get('title')} with {len(plan.get('scenes', []))} scenes")

# Step 2: Submit produce request
produce_req = json.dumps({
    "plan": plan,
    "quality": "balanced",
    "fast_mode": True
}).encode("utf-8")

req2 = urllib.request.Request(
    f"{BASE}/api/ai-video-director/produce",
    data=produce_req,
    headers={"Content-Type": "application/json"},
    method="POST"
)
with urllib.request.urlopen(req2, timeout=120) as resp:
    result = json.loads(resp.read().decode("utf-8"))

job_id = result.get("job_id")
print(f"Produce job started: job_id={job_id}")
print(f"Status URL: {BASE}/api/ai-video-director/produce/{job_id}")

# Step 3: Poll status until done or error
start_time = time.time()
last_stage = ""
while True:
    elapsed = time.time() - start_time
    if elapsed > 1800:  # 30 min timeout
        print(f"\nTIMEOUT after {elapsed:.0f}s")
        break

    try:
        with urllib.request.urlopen(f"{BASE}/api/ai-video-director/produce/{job_id}", timeout=10) as resp:
            status = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  [poll error: {e}]")
        time.sleep(5)
        continue

    job_status = status.get("status", "unknown")
    progress = status.get("progress", 0)
    stage = status.get("stage", "")
    detail = status.get("detail", "")
    elapsed_s = status.get("elapsed_seconds", 0)

    if stage != last_stage:
        print(f"  [{elapsed_s}s] {progress}% — {stage}: {detail}")
        last_stage = stage
    elif int(elapsed) % 30 == 0:
        print(f"  [{elapsed_s}s] {progress}% — {stage}: {detail}")

    if job_status in ("done", "error", "cancelled"):
        print(f"\nFINAL STATUS: {job_status}")
        print(f"  Stage: {stage}")
        print(f"  Detail: {detail}")
        if status.get("error"):
            print(f"  Error: {status['error']}")
        if status.get("result"):
            result_data = status["result"]
            print(f"  Final video: {result_data.get('final_video')}")
            print(f"  Scenes: {len(result_data.get('scenes', []))}")
            for s in result_data.get("scenes", []):
                print(f"    Scene {s.get('id')}: normalized={s.get('normalized')}, skipped={s.get('skipped', False)}")
            print(f"  Final QA: {result_data.get('final_qa', {}).get('passed')}")
        print(f"  Total runtime: {elapsed_s}s")
        break

    time.sleep(3)
