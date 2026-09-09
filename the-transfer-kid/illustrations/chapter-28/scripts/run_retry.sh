#!/bin/bash
# Retry the 3 failed chapter-28 illustrations
cd "$(dirname "$0")/.."

run() {
  local prompt="$1" out="$2" size="$3"
  echo "=== $out ==="
  python3 scripts/generate_web.py --prompt-file "prompts/$prompt" --out "$out" --size "$size"
  if [ $? -ne 0 ]; then
    echo "FAILED: $out (continuing to next)"
  fi
}

run 10-ice-pack.md             10-ice-pack.png              4:3
run 11-phone-notifications.md  11-phone-notifications.png   3:4
run 14-kitchen-table.md        14-kitchen-table.png         4:3

echo "=== RETRY BATCH DONE ==="
