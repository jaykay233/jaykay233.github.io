#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=$(command -v python3)
LABEL="com.archatlas.daily-refresh"
AGENTS="$HOME/Library/LaunchAgents"
LOGS="$HOME/Library/Logs/ArchAtlas"
PLIST="$AGENTS/$LABEL.plist"
mkdir -p "$AGENTS" "$LOGS"

ROOT="$ROOT" PYTHON="$PYTHON" PLIST="$PLIST" LOGS="$LOGS" LABEL="$LABEL" python3 - <<'PY'
import os
import plistlib
from pathlib import Path

root = Path(os.environ["ROOT"])
logs = Path(os.environ["LOGS"])
plist = {
    "Label": os.environ["LABEL"],
    "ProgramArguments": [os.environ["PYTHON"], str(root / "scripts" / "daily_refresh.py")],
    "WorkingDirectory": str(root),
    "StartCalendarInterval": {"Hour": 8, "Minute": 30},
    "RunAtLoad": False,
    "StandardOutPath": str(logs / "daily-refresh.log"),
    "StandardErrorPath": str(logs / "daily-refresh-error.log"),
    "ProcessType": "Background",
    "LowPriorityIO": True,
}
with Path(os.environ["PLIST"]).open("wb") as f:
    plistlib.dump(plist, f)
PY

GUI_UID=$(id -u)
launchctl bootout "gui/$GUI_UID/$LABEL" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$GUI_UID" "$PLIST"
printf 'Daily refresh installed: every day at 08:30 (local time).\nLog: %s/daily-refresh.log\n' "$LOGS"
printf 'To run once now: %s\n' "$ROOT/scripts/daily_refresh.py"
