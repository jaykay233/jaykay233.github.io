#!/usr/bin/env python3
"""Run the daily Hugging Face discovery and conservative config enrichment pipeline."""
from __future__ import annotations

import fcntl
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = Path.home() / "Library" / "Caches" / "ArchAtlas" / "daily-refresh.lock"
JOBS = ("sync_hf_catalog.py", "enrich_architecture.py")


def main() -> int:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("w", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(f"{datetime.now().astimezone().isoformat()} refresh already running; skip", flush=True)
            return 0

        print(f"{datetime.now().astimezone().isoformat()} daily refresh started", flush=True)
        for script in JOBS:
            command = [sys.executable, str(ROOT / "scripts" / script)]
            print(f"\n$ {' '.join(command)}", flush=True)
            result = subprocess.run(command, cwd=ROOT, check=False)
            if result.returncode:
                print(f"ERROR: {script} exited with status {result.returncode}", file=sys.stderr, flush=True)
                return result.returncode
        print(f"\n{datetime.now().astimezone().isoformat()} daily refresh completed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
