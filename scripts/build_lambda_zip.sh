#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output="$1"
feature="$2"
shift 2
python="${PYTHON:-python3}"

locked_version() {
  awk -v name="$1" '
    $0 == "name = \"" name "\"" { found = 1; next }
    found && /^version = / { gsub(/"/, "", $3); print $3; exit }
  ' "$root/poetry.lock"
}

requirements=()
for name in "$@"; do
  version="$(locked_version "$name")"
  if [ -z "$version" ]; then
    echo "$name is missing from poetry.lock" >&2
    exit 1
  fi
  requirements+=("$name==$version")
done

build="$(mktemp -d)"
trap 'rm -rf "$build"' EXIT

"$python" -m pip install \
  --disable-pip-version-check --no-input --quiet \
  --platform manylinux_2_28_aarch64 --platform manylinux2014_aarch64 --implementation cp --python-version 3.13 \
  --only-binary=:all: --no-deps \
  --target "$build" \
  "${requirements[@]}"

mkdir -p "$build/project_hub/$feature"
cp "$root/src/project_hub/__init__.py" "$build/project_hub/__init__.py"
cp "$root"/src/project_hub/"$feature"/*.py "$build/project_hub/$feature/"

find "$build" -name '__pycache__' -type d -prune -exec rm -rf {} +
find "$build" -maxdepth 1 -name '*.dist-info' -type d -exec rm -rf {} +

mkdir -p "$(dirname "$output")"
output="$(cd "$(dirname "$output")" && pwd)/$(basename "$output")"
rm -f "$output"
(cd "$build" && zip --quiet --recurse-paths --symlinks "$output" .)
