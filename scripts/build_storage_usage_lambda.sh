#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output="${1:-$root/dist/storage-usage-lambda.zip}"
python="${PYTHON:-python3}"

locked_version() {
  awk -v name="$1" '
    $0 == "name = \"" name "\"" { found = 1; next }
    found && /^version = / { gsub(/"/, "", $3); print $3; exit }
  ' "$root/poetry.lock"
}

psycopg_version="$(locked_version psycopg)"
binary_version="$(locked_version psycopg-binary)"
if [ -z "$psycopg_version" ] || [ -z "$binary_version" ]; then
  echo "psycopg or psycopg-binary is missing from poetry.lock" >&2
  exit 1
fi

build="$(mktemp -d)"
trap 'rm -rf "$build"' EXIT

"$python" -m pip install \
  --disable-pip-version-check --no-input --quiet \
  --platform manylinux_2_28_aarch64 --platform manylinux2014_aarch64 --implementation cp --python-version 3.13 \
  --only-binary=:all: --no-deps \
  --target "$build" \
  "psycopg==$psycopg_version" "psycopg-binary==$binary_version"

mkdir -p "$build/project_hub/storage_usage"
cp "$root/src/project_hub/__init__.py" "$build/project_hub/__init__.py"
cp "$root"/src/project_hub/storage_usage/*.py "$build/project_hub/storage_usage/"

find "$build" -name '__pycache__' -type d -prune -exec rm -rf {} +
find "$build" -maxdepth 1 -name '*.dist-info' -type d -exec rm -rf {} +

mkdir -p "$(dirname "$output")"
output="$(cd "$(dirname "$output")" && pwd)/$(basename "$output")"
rm -f "$output"
(cd "$build" && zip --quiet --recurse-paths --symlinks "$output" .)
