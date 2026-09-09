#!/usr/bin/env python3
"""Generate one chapter-28 illustration via the Right Code Drawing API
(https://www.rightapi.ai/draw), text-only or image-to-image against an
already-generated (non-real-person) character reference sheet.

Proven request/response contract — see ~/.agents/knowledge/refs/drawing-ai-api.md
"""
import argparse
import base64
import subprocess
import sys
import time

import requests


def get_api_key() -> str:
    res = subprocess.run(
        ["security", "find-generic-password", "-a", "$USER".replace("$USER", __import__("os").environ.get("USER", "")),
         "-s", "drawing-api-key", "-w"],
        capture_output=True, text=True,
    )
    if res.returncode != 0 or not res.stdout.strip():
        print("Error: could not read drawing-api-key from Keychain", file=sys.stderr)
        sys.exit(1)
    return res.stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", default="4:3", help="aspect ratio string, e.g. 4:3 or 3:4")
    ap.add_argument("--image-size", default="2K")
    ap.add_argument("--ref", help="optional local reference image (non-real-person only)")
    ap.add_argument("--max-polls", type=int, default=60)
    args = ap.parse_args()

    key = get_api_key()
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    prompt = open(args.prompt_file, encoding="utf-8").read()

    payload = {
        "model": "gpt-image-2",
        "prompt": prompt,
        "n": 1,
        "size": args.size,
        "imageSize": args.image_size,
        "async": True,
    }
    if args.ref:
        ref_b64 = base64.b64encode(open(args.ref, "rb").read()).decode()
        payload["image"] = [f"data:image/png;base64,{ref_b64}"]

    print(f"Submitting {args.prompt_file} (ref={args.ref or 'none'}, size={args.size})")
    res = requests.post("https://www.rightapi.ai/draw/v1/images/generations", headers=headers, json=payload, timeout=30)
    res.raise_for_status()
    task_id = res.json().get("task_id")
    if not task_id:
        print(f"Error: no task_id in response: {res.text}", file=sys.stderr)
        sys.exit(1)

    poll_url = f"https://www.rightapi.ai/v1/tasks/{task_id}"
    image_url = None
    start = time.time()
    for i in range(args.max_polls):
        time.sleep(3)
        pj = requests.get(poll_url, headers=headers, timeout=30).json()
        if "data" in pj and pj["data"]:
            image_url = pj["data"][0].get("url")
            break
        if pj.get("status") == "failed":
            print(f"FAILED: {pj.get('error', pj)}", file=sys.stderr)
            sys.exit(1)

    if not image_url:
        print("Error: timed out waiting for image", file=sys.stderr)
        sys.exit(1)

    img = requests.get(image_url, timeout=60).content
    with open(args.out, "wb") as f:
        f.write(img)

    duration = round(time.time() - start, 1)
    print(f"SUCCESS: {args.out} ({len(img)} bytes, {duration}s)")


if __name__ == "__main__":
    main()
