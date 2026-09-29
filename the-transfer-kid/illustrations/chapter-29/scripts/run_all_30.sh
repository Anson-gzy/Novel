#!/bin/bash
DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="python3"
SCRIPT="$DIR/scripts/generate_web.py"
REFS="$DIR/../refs/use"

run_one() {
    local name="$1"
    local prompt="$DIR/prompts/${name}.md"
    local out="$DIR/${name}.png"
    local ref="$2"
    local size="${3:-4:3}"

    if [ -f "$out" ]; then
        echo "SKIP: $out already exists"
        return 0
    fi

    echo "==> Generating $name..."
    local cmd=("$PYTHON" "$SCRIPT" "--prompt-file" "$prompt" "--out" "$out" "--size" "$size")
    if [ -n "$ref" ] && [ -f "$ref" ]; then
        cmd+=("--ref" "$ref")
    fi

    "${cmd[@]}"
    local rc=$?
    if [ $rc -ne 0 ]; then
        echo "FAILED: $name (exit code $rc)"
    fi
}

# 30 items
run_one "01-morning-keys" "$REFS/set-apartment.jpg" "4:3"
run_one "02-ceiling-insomnia" "$REFS/justin.jpg" "4:3"
run_one "03-memory-punch-recall" "$REFS/justin.jpg" "4:3"
run_one "04-entryway-clogs" "$REFS/set-apartment.jpg" "4:3"
run_one "05-answering-machine-idle" "" "4:3"
run_one "06-answering-machine-playing" "" "4:3"
run_one "07-bruised-hand-swelling" "$REFS/justin.jpg" "4:3"
run_one "08-hallway-shadow" "$REFS/justin.jpg" "4:3"
run_one "09-mother-counter-dawn" "$REFS/set-apartment.jpg" "4:3"
run_one "10-mother-gaze-hand" "$REFS/justin.jpg" "4:3"
run_one "11-kitchen-stillness-two-shot" "$REFS/justin.jpg" "4:3"
run_one "12-memory-childhood-rug" "" "4:3"
run_one "13-mother-setting-badge" "$REFS/set-apartment.jpg" "4:3"
run_one "14-bedroom-sunlight-morning" "$REFS/set-apartment.jpg" "4:3"
run_one "15-school-absence-contrast" "$REFS/set-cafeteria.jpg" "4:3"
run_one "16-phone-screen-contacts" "$REFS/justin.jpg" "4:3"
run_one "17-shoes-hoodie-prep" "$REFS/justin.jpg" "4:3"
run_one "18-empty-neighborhood-street" "" "4:3"
run_one "19-memory-kicking-cans" "" "4:3"
run_one "20-marcus-house-exterior" "" "4:3"
run_one "21-doorbell-hesitation" "$REFS/justin.jpg" "4:3"
run_one "22-door-unlocking" "" "4:3"
run_one "23-marcus-doorway-face" "$REFS/marcus.jpg" "4:3"
run_one "24-porch-facing-each-other" "$REFS/justin.jpg" "4:3"
run_one "25-justin-looking-down" "$REFS/justin.jpg" "4:3"
run_one "26-showing-injured-knuckles" "$REFS/justin.jpg" "4:3"
run_one "27-marcus-touching-bandage" "$REFS/marcus.jpg" "4:3"
run_one "28-marcus-cold-truth" "$REFS/marcus.jpg" "4:3"
run_one "29-door-latching-unlocked" "" "4:3"
run_one "30-walking-down-valencia" "$REFS/justin.jpg" "4:3"

echo "All 30 illustration tasks completed."
