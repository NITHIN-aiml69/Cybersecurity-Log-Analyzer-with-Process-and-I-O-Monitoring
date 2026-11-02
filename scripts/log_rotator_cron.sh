#!/usr/bin/env bash
# ==============================================================================
# Script: log_rotator_cron.sh
# Purpose: Cron scheduled automated log rotation and storage safety audit
# Author: NITHIN N | Roll Number: 25BTRPW066
# Recommended crontab: 0 * * * * /path/to/log_rotator_cron.sh >> /var/log/sentinel_cron.log 2>&1
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

if [ -x "/usr/local/bin/python3" ]; then
    PYTHON_BIN="/usr/local/bin/python3"
elif [ -x "/usr/bin/python3" ]; then
    PYTHON_BIN="/usr/bin/python3"
else
    PYTHON_BIN="python3"
fi

echo "[$TIMESTAMP] Starting automated hourly log rotation audit..."
"$PYTHON_BIN" "$BASE_DIR/cyber_sentinel.py" rotate
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "[$TIMESTAMP] Log rotation audit finished cleanly."
else
    echo "[$TIMESTAMP] Log rotation encountered warnings or errors (exit $EXIT_CODE)."
fi
exit $EXIT_CODE
