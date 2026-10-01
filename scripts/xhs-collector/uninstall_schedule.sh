#!/bin/bash
set -euo pipefail
PLIST="$HOME/Library/LaunchAgents/com.jaykay233.archatlas-xhs.plist"
launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
rm -f "$PLIST"
echo 'Removed the ArchAtlas XHS daily schedule.'
