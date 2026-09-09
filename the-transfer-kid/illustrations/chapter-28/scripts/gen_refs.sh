#!/bin/bash
# Generate the three original character reference sheets, retrying through the
# upstream cooldown. Justin needs no sheet — assets/Justin.PNG already is one.
cd "$(dirname "$0")/.." || exit 1
GEN="$HOME/.agents/skills/sub2api-imagegen/scripts/generate.py"

for name in samira marcus andrew; do
  out="refs/$name.png"
  [ -f "$out" ] && { echo "SKIP $name (exists)"; continue; }
  for attempt in $(seq 1 40); do
    echo "=== $name attempt $attempt $(date +%H:%M:%S) ==="
    if python3 "$GEN" --prompt "$(cat "refs/$name.txt")" --size 1:1 --out "$out" 2>&1 | tail -5; then
      [ -f "$out" ] && { echo "OK $name"; break; }
    fi
    grep -q . /dev/null
    echo "retry in 90s"
    sleep 90
  done
  [ -f "$out" ] || echo "FAILED $name"
done
echo "=== refs done ==="
ls -la refs/
