#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
UPSTREAM="$HOME/.local/share/archatlas/Spider_XHS"
mkdir -p "$(dirname "$UPSTREAM")"
if [ ! -d "$UPSTREAM/.git" ]; then
  git clone https://github.com/cv-cat/Spider_XHS.git "$UPSTREAM"
else
  echo "Using existing Spider_XHS checkout at $UPSTREAM"
fi
python3 -m venv "$ROOT/.xhs-venv"
"$ROOT/.xhs-venv/bin/python" -m pip install --upgrade pip
"$ROOT/.xhs-venv/bin/pip" install -r "$UPSTREAM/requirements.txt" keyring
printf '\nSetup complete. Next run:\n  cd "%s"\n  SPIDER_XHS_PATH="%s" .xhs-venv/bin/python scripts/xhs-collector/collect_questions.py --login\n' "$ROOT" "$UPSTREAM"
echo 'The QR login stays on this Mac; it is not uploaded to GitHub.'
