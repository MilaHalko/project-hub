#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output="${1:-$root/dist/storage-usage-lambda.zip}"

exec bash "$root/scripts/build_lambda_zip.sh" "$output" storage_usage psycopg psycopg-binary
