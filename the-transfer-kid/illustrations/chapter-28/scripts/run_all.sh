#!/bin/bash
# Chapter 28 illustration batch driver (v2, parallel).
# Usage: run_all.sh [parallelism]      default 4
#        run_all.sh --one "name|size|ref ref"   (internal, one image)

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CH28_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROMPTS="$CH28_DIR/prompts"
GEN="$HOME/.agents/skills/sub2api-imagegen/scripts/generate.py"
USE="$CH28_DIR/../refs/use"

# ---------------------------------------------------------------- worker mode
if [ "${1:-}" = "--one" ]; then
  IFS='|' read -r name size refs <<< "$2"
  out_file="$CH28_DIR/$name.png"
  # Quota is scarce; a resumed run must not re-spend it on images already done.
  [ -f "$out_file" ] && { echo "SKIP $name (exists)"; exit 0; }

  cmd=(python3 "$GEN" --prompt "$(cat "$PROMPTS/$name.md")" --out "$out_file" --size "$size")
  # One --ref carrying every path. generate.py's --ref is nargs="+", so a flag
  # per reference used to keep only the last one and silently drop the rest.
  if [ -n "$refs" ]; then
    cmd+=(--ref)
    for r in $refs; do cmd+=("$USE/$r.jpg"); done
  fi

  # The upstream shares one credential across all workers, so a failure is
  # usually "the whole pool is in cooldown", not "this image is bad". Back off
  # with jitter so four workers do not stampede the reset.
  # Never discard stderr here: "quota cooldown" and "content rejected" both look
  # like a missing file, but one means wait and the other means rewrite the shot.
  log="$CH28_DIR/../refs/use/errors.log"
  for attempt in 1 2 3 4 5 6 7 8 9 10; do
    err=$("${cmd[@]}" 2>&1 | grep -E "HTTP Error|moderation|error" | head -2)
    if [ -f "$out_file" ]; then
      echo "OK   $name (attempt $attempt)"
      exit 0
    fi
    echo "$(date +%H:%M:%S) $name attempt $attempt: ${err:-unknown}" >> "$log"
    sleep $(( 60 + RANDOM % 60 ))
  done
  echo "FAIL $name — last error: $(tail -1 "$log")"
  exit 1
fi

# ------------------------------------------------------------ dispatcher mode
PAR="${1:-4}"
mkdir -p "$USE"
compress() {  # compress <src> <dest-basename>
  local dst="$USE/$2.jpg"
  [ -f "$dst" ] || sips -s format jpeg -s formatOptions 80 "$1" --out "$dst" >/dev/null 2>&1
}
# Reference sheets are compressed to JPEG before use as --ref: the raw PNGs are
# 2-3 MB each and base64 payloads that size fail on the gateway (baoyu-comic
# Step 7.1 warns about exactly this). ~2.4 MB -> ~0.4 MB.
# Character designs supplied by the author live with the project's other source
# art in assets/; sheets we generated and the location sheets live in
# illustrations/refs/. Both are PROJECT-level: chapter 29 reuses them as-is,
# which is the whole point — re-establishing a character per chapter is what
# made the faces drift in v1.
# Character refs come from refs/clean/ — neutralised sheets (face only: no hat, no
# wardrobe, flat light, empty background). The author's original art in assets/ is
# the identity source but carries a hat, a coloured tee and hard blind-stripe light,
# and img2img drags all of that into every scene, outvoting the prompt text.
REFS="$CH28_DIR/../refs"
compress "$REFS/clean/justin.png"    justin
compress "$REFS/clean/marcus.png"    marcus
compress "$REFS/clean/andrew.png"    andrew
compress "$REFS/clean/samira.png"    samira
compress "$REFS/clean/zack.png"      zack
compress "$REFS/set-apartment.png"   set-apartment
compress "$REFS/set-cafeteria.png"   set-cafeteria

# name|size|refs   — refs are basenames under refs/use/, space separated.
# The location sheets keep the apartment and the cafeteria from drifting across
# the 9 interior shots and the 2 flashbacks; repeated prose alone will not.
# 20-zack is out of numeric order on purpose: it slots between 13 and 14 in the
# chapter, but renumbering the existing files would invalidate every prompt path.
TASKS='
01-train|4:3|justin
02-window-reflection|4:3|justin
03-suspension-slip|3:4|justin
04-east-gate|4:3|justin andrew
05-stairs|4:3|justin
06-empty-apartment|4:3|justin set-apartment
07-index-card|3:4|set-apartment
08-answering-machine|3:4|set-apartment
09-freezer|4:3|justin set-apartment
10-ice-pack|4:3|justin
11-phone-notifications|3:4|justin
12-marcus-turning|4:3|justin marcus set-cafeteria
13-cafeteria-after|4:3|justin marcus set-cafeteria
20-zack|4:3|zack
14-marcus-lying|4:3|marcus
15-urgent-care|4:3|marcus
16-samira-door|4:3|justin samira
17-kitchen-table|4:3|justin samira set-apartment
18-samira-leaving|4:3|justin samira set-apartment
19-closing|3:4|justin set-apartment
'

echo "$TASKS" | grep -v '^$' \
  | xargs -P "$PAR" -I{} bash "$SCRIPT_DIR/run_all.sh" --one "{}"
rc=$?

echo ""
missing=$(echo "$TASKS" | grep -v '^$' | cut -d'|' -f1 \
  | while read -r n; do [ -f "$CH28_DIR/$n.png" ] || echo "$n"; done)
if [ -n "$missing" ]; then
  echo "MISSING:"; echo "$missing"; exit 1
fi
echo "ALL 20 IMAGES DONE"
exit 0
