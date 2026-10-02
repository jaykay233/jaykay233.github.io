#!/bin/bash
set -euo pipefail
export PATH="$HOME/.local/share/archatlas/node-v22.23.3/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
UPSTREAM="$HOME/.local/share/archatlas/Spider_XHS"
cd "$ROOT"
export SPIDER_XHS_PATH="$UPSTREAM"
# Bring the checkout forward before writing today's snapshot.
git pull --rebase origin master
"$ROOT/.xhs-venv/bin/python" scripts/xhs-collector/collect_questions.py
if git diff --quiet -- interview-questions/data/questions.json; then
  echo "Question index unchanged."
  exit 0
fi
git add interview-questions/data/questions.json
git -c user.name='ArchAtlas local collector' -c user.email='archatlas-local@users.noreply.github.com' commit -m "chore: refresh AI infra interview index"
git push origin HEAD:master
