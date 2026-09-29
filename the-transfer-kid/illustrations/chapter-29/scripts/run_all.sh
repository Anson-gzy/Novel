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

run_one "01-morning-keys" "$REFS/set-apartment.jpg" "4:3"
run_one "02-answering-machine" "" "4:3"
run_one "03-kitchen-dawn" "$REFS/justin.jpg" "4:3"
run_one "04-bedroom-sunlight" "$REFS/justin.jpg" "4:3"
run_one "05-neighborhood-walk" "$REFS/justin.jpg" "4:3"
run_one "06-marcus-doorstep" "$REFS/marcus.jpg" "4:3"
run_one "07-porch-apology" "$REFS/justin.jpg" "4:3"
run_one "08-walking-home" "$REFS/justin.jpg" "4:3"

echo "All generation tasks completed."
