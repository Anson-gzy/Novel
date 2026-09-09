#!/bin/bash
# Mirror local git repos to bare repos on the NAS over SSH.
#
#   NAS_HOST=gzy@192.168.3.114 NAS_GIT_DIR=/vol1/git ./mirror_to_nas.sh repos.txt
#   ./mirror_to_nas.sh repos.txt --dry-run
#
# repos.txt: one absolute repo path per line, blank lines and #comments ignored.
# Pushes with --mirror, so the NAS copy is a full backup: every branch, every tag.
# Re-running updates in place; it is safe to run repeatedly.
set -uo pipefail

HOST="${NAS_HOST:?set NAS_HOST, e.g. gzy@192.168.3.114}"
GITDIR="${NAS_GIT_DIR:-/vol1/git}"
LIST="${1:?usage: mirror_to_nas.sh <repos.txt> [--dry-run]}"
DRY=""
[ "${2:-}" = "--dry-run" ] && DRY=1

ok=0; failed=0; failed_list=""

while IFS= read -r repo; do
  repo="${repo%%#*}"; repo="$(echo "$repo" | xargs)"
  [ -z "$repo" ] && continue
  if [ ! -d "$repo/.git" ]; then
    echo "SKIP  $repo (not a git repo)"; continue
  fi

  # Bare repo name: the directory name, spaces folded to dashes so the remote
  # path needs no quoting on the far side.
  name="$(basename "$repo" | tr ' ' '-')"
  remote="$HOST:$GITDIR/$name.git"

  if [ -n "$DRY" ]; then
    echo "WOULD $repo  ->  $remote"
    continue
  fi

  echo "=== $name ==="
  # init --bare is idempotent on an existing bare repo.
  if ! ssh "$HOST" "mkdir -p '$GITDIR/$name.git' && git init --bare -q '$GITDIR/$name.git'"; then
    echo "FAIL  $name (could not create remote repo)"
    failed=$((failed+1)); failed_list="$failed_list $name"; continue
  fi
  if git -C "$repo" push --mirror "$remote"; then
    echo "OK    $name"
    ok=$((ok+1))
  else
    echo "FAIL  $name (push)"
    failed=$((failed+1)); failed_list="$failed_list $name"
  fi
done < "$LIST"

echo ""
echo "mirrored=$ok failed=$failed"
[ -n "$failed_list" ] && echo "failures:$failed_list"
[ "$failed" -eq 0 ]
