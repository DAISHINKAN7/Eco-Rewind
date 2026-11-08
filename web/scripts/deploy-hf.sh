#!/usr/bin/env bash
# Build the site and upload it to a Hugging Face static Space. Usage: bash scripts/deploy-hf.sh <user>/<space-name>
# Needs: `pip install -U huggingface_hub` and `hf auth login` (a write token). Data must be in public/data first,
# or build with VITE_DATA_BASE pointing at an external data host.
set -euo pipefail
SPACE="${1:?usage: deploy-hf.sh <user>/<space-name>}"
cd "$(dirname "$0")/.."
npm run build
cp deploy/huggingface/README.md dist/README.md
python3 -c "from huggingface_hub import create_repo; create_repo('$SPACE', repo_type='space', space_sdk='static', exist_ok=True)"
hf upload "$SPACE" dist . --repo-type space --commit-message "EcoRewind site build"
echo "https://huggingface.co/spaces/$SPACE"
