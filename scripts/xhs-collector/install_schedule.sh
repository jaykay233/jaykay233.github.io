#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.jaykay233.archatlas-xhs.plist"
LOG_DIR="$HOME/Library/Logs/ArchAtlasXHS"
mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"
cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.jaykay233.archatlas-xhs</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$ROOT/scripts/xhs-collector/run_daily.sh</string></array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>$LOG_DIR/collector.log</string>
  <key>StandardErrorPath</key><string>$LOG_DIR/collector-error.log</string>
</dict></plist>
PLIST
launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Installed daily 09:00 local job: $PLIST"
echo "Logs: $LOG_DIR"
