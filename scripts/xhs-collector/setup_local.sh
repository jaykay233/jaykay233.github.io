#!/bin/bash
set -euo pipefail
export PATH="$HOME/.local/share/archatlas/node-v22.23.3/bin:$PATH"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1 || ! "$PYTHON_BIN" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "Python 3.10+ is required. Set PYTHON_BIN, for example: PYTHON_BIN=python3.12 bash scripts/xhs-collector/setup_local.sh" >&2
  exit 1
fi
if ! command -v node >/dev/null 2>&1 || ! node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 20 ? 0 : 1)'; then
  echo "Node.js 20+ is required by Spider_XHS signing runtime. Install Node and rerun setup." >&2
  exit 1
fi
UPSTREAM="$HOME/.local/share/archatlas/Spider_XHS"
mkdir -p "$(dirname "$UPSTREAM")"
if [ ! -d "$UPSTREAM/.git" ]; then
  git clone https://github.com/cv-cat/Spider_XHS.git "$UPSTREAM"
else
  echo "Using existing Spider_XHS checkout at $UPSTREAM"
fi
# Spider_XHS' local Node signing runtime requires its npm dependency (crypto-js).
npm --prefix "$UPSTREAM" install --no-audit --no-fund
"$PYTHON_BIN" -m venv "$ROOT/.xhs-venv"
"$ROOT/.xhs-venv/bin/python" -m pip install --upgrade pip
"$ROOT/.xhs-venv/bin/pip" install -r "$UPSTREAM/requirements.txt" keyring
printf '\nSetup complete. Next run:\n  cd "%s"\n  SPIDER_XHS_PATH="%s" .xhs-venv/bin/python scripts/xhs-collector/collect_questions.py --login\n' "$ROOT" "$UPSTREAM"
echo 'The QR login stays on this Mac; it is not uploaded to GitHub.'
