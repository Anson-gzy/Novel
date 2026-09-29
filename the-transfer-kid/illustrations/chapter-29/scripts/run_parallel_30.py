#!/usr/bin/env python3
"""
Standard Chapter Illustration Generator using sub2api-imagegen skill.
"""
import concurrent.futures
import subprocess
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent
PYTHON = sys.executable
SUB2API_GENERATE = Path.home() / ".agents/skills/sub2api-imagegen/scripts/generate.py"
REFS = DIR.parent / "refs/use"

TASKS = [
    ("01-morning-keys", str(REFS / "set-apartment.jpg"), "4:3"),
    ("02-ceiling-insomnia", str(REFS / "justin.jpg"), "4:3"),
    ("03-memory-punch-recall", str(REFS / "justin.jpg"), "4:3"),
    ("04-entryway-clogs", str(REFS / "set-apartment.jpg"), "4:3"),
    ("05-answering-machine-idle", "", "4:3"),
    ("06-answering-machine-playing", "", "4:3"),
    ("07-bruised-hand-swelling", str(REFS / "justin.jpg"), "4:3"),
    ("08-hallway-shadow", str(REFS / "justin.jpg"), "4:3"),
    ("09-mother-counter-dawn", str(REFS / "set-apartment.jpg"), "4:3"),
    ("10-mother-gaze-hand", str(REFS / "justin.jpg"), "4:3"),
    ("11-kitchen-stillness-two-shot", str(REFS / "justin.jpg"), "4:3"),
    ("12-memory-childhood-rug", "", "4:3"),
    ("13-mother-setting-badge", str(REFS / "set-apartment.jpg"), "4:3"),
    ("14-bedroom-sunlight-morning", str(REFS / "set-apartment.jpg"), "4:3"),
    ("15-school-absence-contrast", str(REFS / "set-cafeteria.jpg"), "4:3"),
    ("16-phone-screen-contacts", str(REFS / "justin.jpg"), "4:3"),
    ("17-shoes-hoodie-prep", str(REFS / "justin.jpg"), "4:3"),
    ("18-empty-neighborhood-street", "", "4:3"),
    ("19-memory-kicking-cans", "", "4:3"),
    ("20-marcus-house-exterior", "", "4:3"),
    ("21-doorbell-hesitation", str(REFS / "justin.jpg"), "4:3"),
    ("22-door-unlocking", "", "4:3"),
    ("23-marcus-doorway-face", str(REFS / "marcus.jpg"), "4:3"),
    ("24-porch-facing-each-other", str(REFS / "justin.jpg"), "4:3"),
    ("25-justin-looking-down", str(REFS / "justin.jpg"), "4:3"),
    ("26-showing-injured-knuckles", str(REFS / "justin.jpg"), "4:3"),
    ("27-marcus-touching-bandage", str(REFS / "marcus.jpg"), "4:3"),
    ("28-marcus-cold-truth", str(REFS / "marcus.jpg"), "4:3"),
    ("29-door-latching-unlocked", "", "4:3"),
    ("30-walking-down-valencia", str(REFS / "justin.jpg"), "4:3"),
]


def run_one(item):
    name, ref, size = item
    prompt_file = DIR / "prompts" / f"{name}.md"
    out = DIR / f"{name}.png"

    if out.is_file() and out.stat().st_size > 10000:
        print(f"[SKIP] {name} already exists ({out.stat().st_size} bytes)")
        return name, True

    prompt_text = prompt_file.read_text(encoding="utf-8")
    cmd = [
        PYTHON,
        str(SUB2API_GENERATE),
        "--prompt", prompt_text,
        "--out", str(out),
        "--size", size,
        "--model", "gpt-image-2",
        "--quality", "high",
    ]
    if ref and Path(ref).is_file():
        cmd.extend(["--ref", ref])

    print(f"[START] {name} via sub2api...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print(f"[SUCCESS] {name}")
        return name, True
    else:
        print(f"[FAILED] {name}: {res.stderr.strip() or res.stdout.strip()}")
        return name, False


def main():
    print(f"Starting sub2api parallel generation of {len(TASKS)} illustrations (workers=4)...")
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(run_one, t): t[0] for t in TASKS}
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                name, ok = future.result()
                results[name] = ok
            except Exception as exc:
                print(f"[ERROR] {name} generated an exception: {exc}")
                results[name] = False

    passed = sum(1 for v in results.values() if v)
    print(f"\nCompleted: {passed}/{len(TASKS)} illustrations via Sub2API.")


if __name__ == "__main__":
    main()
