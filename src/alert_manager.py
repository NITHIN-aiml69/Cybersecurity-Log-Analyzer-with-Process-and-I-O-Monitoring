#!/usr/bin/env python3
"""
Central Alert & Incident Correlation Subsystem (CO2, CO4, CO5, CO6)
Author: NITHIN N | Roll Number: 25BTRPW066
Correlates security authentication failures with abnormal CPU/memory/I/O telemetry,
detecting coordinated cyber intrusions (e.g. SSH intrusion leading to a crypto miner or ransomware).
"""

import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Any


@dataclass
class CorrelatedIncident:
    incident_id: str
    timestamp: str
    severity: str  # "INFO", "WARNING", "CRITICAL"
    category: str  # "AUTH_BREACH", "PROCESS_ANOMALY", "IO_BURST", "COORDINATED_ATTACK"
    title: str
    details: str
    source_indicators: Dict[str, Any] = field(default_factory=dict)
    remediation_suggestion: str = ""


class AlertManager:
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.incidents: List[CorrelatedIncident] = []
        self._max_history = 100
        self._incident_counter = 1000

    def record_incident(
        self,
        severity: str,
        category: str,
        title: str,
        details: str,
        indicators: Optional[Dict[str, Any]] = None,
        remediation: str = ""
    ) -> CorrelatedIncident:
        """Records an incident and adds it to the ring buffer."""
        self._incident_counter += 1
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        inc = CorrelatedIncident(
            incident_id=f"INC-{self._incident_counter}",
            timestamp=now_str,
            severity=severity,
            category=category,
            title=title,
            details=details,
            source_indicators=indicators or {},
            remediation_suggestion=remediation
        )
        self.incidents.append(inc)
        if len(self.incidents) > self._max_history:
            self.incidents.pop(0)
        return inc

    def correlate_telemetry(
        self,
        security_alerts: list,
        rogue_processes: list,
        io_metrics: Any,
        memory_metrics: Any
    ) -> List[CorrelatedIncident]:
        """
        Cross-correlates security events with OS telemetry.
        Example: SSH attack + High CPU process = Coordinated Cryptojacking Intrusion
        Example: Unauthorized sudo + High disk write = Ransomware Execution
        """
        new_incidents = []

        has_auth_attack = any(a.rule_name == "SSH_BRUTE_FORCE_ATTACK" for a in security_alerts)
        has_sudo_attack = any("SUDO" in a.rule_name for a in security_alerts)
        has_payload = any(a.rule_name == "SUSPICIOUS_PAYLOAD_DETECTED" for a in security_alerts)

        # 1. Check for Coordinated Cryptojacking / Botnet
        if (has_auth_attack or has_payload) and rogue_processes:
            high_cpu_procs = [p for p in rogue_processes if p.cpu_percent >= 60.0]
            if high_cpu_procs:
                p = high_cpu_procs[0]
                inc = self.record_incident(
                    severity="CRITICAL",
                    category="COORDINATED_ATTACK",
                    title="CRITICAL: Post-Compromise Cryptominer / CPU Hijack Detected",
                    details=(
                        f"External authentication/payload attack coincided with rogue high CPU process "
                        f"'{p.name}' (PID: {p.pid}, CPU: {p.cpu_percent}%). "
                        f"Indicates successful intrusion resulting in compute resource hijacking."
                    ),
                    indicators={"pid": p.pid, "name": p.name, "cpu": p.cpu_percent, "cmd": p.cmdline},
                    remediation=f"De-prioritize (renice +19) or terminate PID {p.pid} immediately; block attacker IP at firewall."
                )
                new_incidents.append(inc)

        # 2. Check for Ransomware / Mass Disk Encryption
        if (has_auth_attack or has_sudo_attack or has_payload) and io_metrics and io_metrics.write_mbs >= 20.0:
            inc = self.record_incident(
                severity="CRITICAL",
                category="COORDINATED_ATTACK",
                title="CRITICAL: Potential Ransomware Bulk Encryption Burst Detected",
                details=(
                    f"Authentication violation accompanied by an abnormal write burst of "
                    f"{io_metrics.write_mbs} MB/s and elevated I/O wait ({io_metrics.iowait_pct}%)."
                ),
                indicators={"write_mbs": io_metrics.write_mbs, "iowait": io_metrics.iowait_pct},
                remediation="Freeze filesystem write access, isolate network interface, inspect active file write descriptors."
            )
            new_incidents.append(inc)

        # 3. Standalone Rogue Process Alerts
        for p in rogue_processes:
            # Avoid duplicating if already correlated
            if not any(getattr(i, 'source_indicators', {}).get("pid") == p.pid for i in self.incidents[-5:]):
                inc = self.record_incident(
                    severity="WARNING" if p.cpu_percent < 80 else "CRITICAL",
                    category="PROCESS_ANOMALY",
                    title=f"Rogue Process Flagged: {p.name} (PID: {p.pid})",
                    details=f"Process triggered triggers: {'; '.join(p.suspicious_reasons)}",
                    indicators={"pid": p.pid, "name": p.name, "cpu": p.cpu_percent, "rss_mb": p.memory_rss_mb},
                    remediation="Inspect process lineage via PPID, check open network ports, renice or kill if unauthorized."
                )
                new_incidents.append(inc)

        # 4. Standalone I/O Anomalies
        if io_metrics and io_metrics.is_anomaly:
            for reason in io_metrics.anomaly_reasons:
                inc = self.record_incident(
                    severity="WARNING",
                    category="IO_BURST",
                    title="Storage Subsystem Alert",
                    details=reason,
                    indicators={"write_mbs": io_metrics.write_mbs, "iowait": io_metrics.iowait_pct},
                    remediation="Check top disk consumers via iostat or /proc/[pid]/io."
                )
                new_incidents.append(inc)

        # 5. Standalone Memory Alerts
        if memory_metrics and memory_metrics.is_critical:
            inc = self.record_incident(
                severity="CRITICAL",
                category="PROCESS_ANOMALY",
                title="Memory Exhaustion Threat (OOM Imminent)",
                details=f"System RAM utilization reached {memory_metrics.utilization_pct}%.",
                indicators={"utilization": memory_metrics.utilization_pct, "free_mb": memory_metrics.free_mb},
                remediation="Trigger page cache drop or kill top memory-consuming processes to avoid Linux OOM killer panic."
            )
            new_incidents.append(inc)

        return new_incidents

    def get_recent_incidents(self, limit: int = 15) -> List[CorrelatedIncident]:
        """Returns the most recent correlated incidents."""
        return self.incidents[-limit:]


if __name__ == "__main__":
    am = AlertManager()
    inc = am.record_incident(
        severity="CRITICAL",
        category="COORDINATED_ATTACK",
        title="Test Incident Alert",
        details="Sample incident correlation test.",
        remediation="Sample remediation action."
    )
    print(f"Recorded: [{inc.severity}] {inc.incident_id}: {inc.title}")
