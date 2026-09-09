#!/bin/bash
# Generate the two location reference sheets (apartment, cafeteria), retrying
# through upstream cooldown. Run AFTER gen_refs.sh so we never hold two slots.
cd "$(dirname "$0")/.." || exit 1
GEN="$HOME/.agents/skills/sub2api-imagegen/scripts/generate.py"

for name in set-apartment set-cafeteria; do
  out="refs/$name.png"
  [ -f "$out" ] && { echo "SKIP $name (exists)"; continue; }
  for attempt in $(seq 1 40); do
    echo "=== $name attempt $attempt $(date +%H:%M:%S) ==="
    python3 "$GEN" --prompt "$(cat "refs/$name.txt")" --size 4:3 --out "$out" 2>&1 | tail -5
    [ -f "$out" ] && { echo "OK $name"; break; }
    echo "retry in 90s"
    sleep 90
  done
  [ -f "$out" ] || echo "FAILED $name"
done
echo "=== sets done ==="
ls -la refs/
