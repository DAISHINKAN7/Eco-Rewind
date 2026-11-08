#!/usr/bin/env bash
# Copy the published site data (results, maps, layers, pixel samples, lab models; ~1 GB) from the repository's
# gh-pages branch into web/public/data so `npm run dev` shows real data. Usage: bash scripts/fetch-data.sh [repo-url]
set -euo pipefail
REPO="${1:-https://github.com/DAISHINKAN7/EcoRewind2.git}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git clone --depth 1 --branch gh-pages --filter=blob:none --sparse "$REPO" "$TMP/site"
git -C "$TMP/site" sparse-checkout set data
mkdir -p "$HERE/public/data"
cp -R "$TMP/site/data/." "$HERE/public/data/"
du -sh "$HERE/public/data"
echo "data ready in web/public/data"
