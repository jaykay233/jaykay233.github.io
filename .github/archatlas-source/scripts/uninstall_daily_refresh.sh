#!/bin/sh
set -eu
LABEL="com.archatlas.daily-refresh"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
GUI_UID=$(id -u)
launchctl bootout "gui/$GUI_UID/$LABEL" >/dev/null 2>&1 || true
rm -f "$PLIST"
printf 'Daily refresh schedule removed. Logs and fetched data were kept.\n'
