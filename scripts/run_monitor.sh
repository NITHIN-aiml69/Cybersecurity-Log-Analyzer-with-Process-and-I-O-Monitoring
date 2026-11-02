#!/usr/bin/env bash
# ==============================================================================
# Script: run_monitor.sh
# Purpose: Master interactive launcher for Cyber Sentinel
# Author: NITHIN N | Roll Number: 25BTRPW066
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"

# Determine Python binary
if [ -x "/usr/local/bin/python3" ]; then
    PYTHON_BIN="/usr/local/bin/python3"
elif [ -x "/usr/bin/python3" ]; then
    PYTHON_BIN="/usr/bin/python3"
else
    PYTHON_BIN="python3"
fi

show_menu() {
    clear
    echo -e "\033[1;36m==============================================================================\033[0m"
    echo -e "\033[1;32m      CYBER SENTINEL: CYBERSECURITY LOG ANALYZER & OS MONITOR\033[0m"
    echo -e "\033[1;37m      Student: NITHIN N  |  Roll Number: 25BTRPW066\033[0m"
    echo -e "\033[1;34m      Course Outcomes: CO2, CO4, CO5, CO6\033[0m"
    echo -e "\033[1;36m==============================================================================\033[0m"
    echo -e " Select an option to execute:"
    echo -e "  \033[1;33m[1]\033[0m Run Single Security & OS Telemetry Audit (Scan)"
    echo -e "  \033[1;33m[2]\033[0m Launch Live Interactive Terminal Dashboard (Monitor)"
    echo -e "  \033[1;33m[3]\033[0m Launch Cyber Web Dashboard (HTTP port 8080)"
    echo -e "  \033[1;33m[4]\033[0m Run Full Attack & Load Simulation Suite"
    echo -e "  \033[1;33m[5]\033[0m Check & Perform Safe Copytruncate Log Rotation"
    echo -e "  \033[1;33m[6]\033[0m Run Automated Unit & Integration Tests (CO2-CO6 Validation)"
    echo -e "  \033[1;33m[0]\033[0m Exit"
    echo -e "\033[1;36m==============================================================================\033[0m"
    echo -n " Enter choice [0-6]: "
}

if [ $# -gt 0 ]; then
    CHOICE="$1"
else
    show_menu
    read -r CHOICE
fi

case "$CHOICE" in
    1)
        "$PYTHON_BIN" "$BASE_DIR/cyber_sentinel.py" scan
        ;;
    2)
        "$PYTHON_BIN" "$BASE_DIR/cyber_sentinel.py" monitor
        ;;
    3)
        "$PYTHON_BIN" "$BASE_DIR/cyber_sentinel.py" web --port 8080
        ;;
    4)
        bash "$SCRIPT_DIR/simulate_attacks.sh"
        ;;
    5)
        "$PYTHON_BIN" "$BASE_DIR/cyber_sentinel.py" rotate --force
        ;;
    6)
        "$PYTHON_BIN" "$BASE_DIR/tests/test_all.py"
        ;;
    0)
        echo -e "\nExiting. Thank you!"
        exit 0
        ;;
    *)
        echo -e "\nInvalid option."
        exit 1
        ;;
esac
