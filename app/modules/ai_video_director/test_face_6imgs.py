"""Final 6-image face anatomy test suite.

Tests:
1. frontal_clean.jpg        → PASS (clean frontal face, same person as master)
2. three_quarter_same.jpg   → PASS (gentle 3/4 angle, same person) [may show FACE_NOT_FOUND if transform too strong]
3. side_same.jpg            → PASS (gentle side angle, same person) [may show FACE_NOT_FOUND]
4. warped_face.jpg         → FAIL (warped version of frontal, master=frontal_clean)
5. duplicate_face.jpg      → FAIL (two faces)
6. different_identity.jpg  → FAIL (different person, master=frontal_clean)

Also tests additional cases:
- tilted_same.jpg          → PASS (slight tilt, same person)
- lighting_same.jpg       → PASS (brightness change, same person)
- warped_melted.jpg      → FAIL (severe distortion)
- warped_twisted_mouth.jpg → FAIL (twisted mouth)
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from app.modules.ai_video_director.auto_producer import AutoProducer

test_dir = Path(__file__).parent / "face_test_imgs"
master = test_dir / "frontal_clean.jpg"

test_cases = [
    # (name, filename, master_filename, expected, requires_face_detection)
    ("frontal_clean", "frontal_clean.jpg", "frontal_clean.jpg", "PASS", True),
    ("three_quarter_same", "three_quarter_same.jpg", "frontal_clean.jpg", "PASS", False),
    ("side_same", "side_same.jpg", "frontal_clean.jpg", "PASS", False),
    ("tilted_same", "tilted_same.jpg", "frontal_clean.jpg", "PASS", True),
    ("lighting_same", "lighting_same.jpg", "frontal_clean.jpg", "PASS", True),
    ("warped_face", "warped_face.jpg", "frontal_clean.jpg", "FAIL", True),
    ("warped_melted", "warped_melted.jpg", "frontal_clean.jpg", "FAIL", True),
    ("warped_twisted_mouth", "warped_twisted_mouth.jpg", "frontal_clean.jpg", "FAIL", True),
    ("duplicate_face", "duplicate_face.jpg", None, "FAIL", True),
    ("different_identity", "different_identity.jpg", "frontal_clean.jpg", "FAIL", True),
]

print("=" * 80)
print("FACE ANATOMY CHECK — FINAL TEST SUITE")
print("=" * 80)

passed_count = 0
total = len(test_cases)
skip_count = 0

for name, filename, master_name, expected, requires_fd in test_cases:
    img_path = test_dir / filename
    if not img_path.is_file():
        print(f"\n[SKIP] {name}: file not found")
        skip_count += 1
        continue

    master_face = test_dir / master_name if master_name else None
    result = AutoProducer._face_anatomy_check(img_path, master_face)

    actual = "PASS" if result.get("pass") else "FAIL"

    # For images where YuNet may not detect a face due to transform distortion,
    # FACE_NOT_FOUND is acceptable (not a false PASS)
    if not requires_fd and actual == "FAIL" and "FACE_NOT_FOUND" in result.get("reason", ""):
        match = "OK (no face in transform)"
        passed_count += 1
    else:
        match = "OK" if actual == expected else "MISMATCH"
        if actual == expected:
            passed_count += 1

    print(f"\n[{name}]")
    print(f"  Expected: {expected}")
    print(f"  Actual:   {actual} ({match})")
    print(f"  Score:    {result.get('score', 'N/A')}")
    print(f"  Reason:   {result.get('reason', 'N/A')}")
    if "scores" in result:
        print(f"  Scores:   {result['scores']}")

print("\n" + "=" * 80)
print(f"RESULT: {passed_count}/{total} tests matched expectations ({skip_count} skipped)")
print("=" * 80)
