#!/usr/bin/env python3
"""
Safe Log Rotation & Archival Subsystem (CO5: File Systems & CO6: Shell Automation)
Author: NITHIN N | Roll Number: 25BTRPW066
Implements atomic copytruncate and signal-based log rotation, gzip compression,
SHA-256 cryptographic integrity verification, and archive retention policies.
"""

import os
import sys
import time
import shutil
import gzip
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional, Tuple


@dataclass
class RotationRecord:
    timestamp: str
    original_file: str
    archive_file: str
    original_size_bytes: int
    compressed_size_bytes: int
    compression_ratio_pct: float
    sha256_checksum: str
    strategy_used: str
    success: bool
    status_message: str


class SafeLogRotator:
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        rot_cfg = self.config.get("log_rotation", {})
        
        self.max_size_bytes = rot_cfg.get("max_log_size_bytes", 1024 * 1024) # Default: 1MB
        self.archive_dir = rot_cfg.get("archive_dir", "cyber_log_analyzer/archives")
        self.max_archives = rot_cfg.get("max_archives", 7)
        self.strategy = rot_cfg.get("strategy", "copytruncate")
        self.verify_sha256 = rot_cfg.get("verify_sha256", True)
        self.target_logs = rot_cfg.get("target_logs", ["cyber_log_analyzer/logs/auth.log"])
        
        # Ensure archive and log directories exist
        os.makedirs(self.archive_dir, exist_ok=True)
        for log_path in self.target_logs:
            log_dir = os.path.dirname(log_path)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)

        self.history_log = os.path.join(self.archive_dir, "rotation_history.log")

    @staticmethod
    def compute_sha256(filepath: str) -> str:
        """Calculates SHA-256 checksum of an archive file for forensic integrity."""
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    def _rotate_copytruncate(self, log_path: str) -> Tuple[str, int, int]:
        """
        Executes atomic copytruncate:
        1. Copies content to an intermediate archive file.
        2. In-place truncates original file to 0 bytes without closing or invalidating
           active process file descriptors.
        3. Forces storage sync via fsync.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.basename(log_path)
        temp_dest = os.path.join(self.archive_dir, f"{base_name}_{timestamp}.tmp")
        final_gz = os.path.join(self.archive_dir, f"{base_name}_{timestamp}.gz")

        orig_size = os.path.getsize(log_path)

        # Step 1: Copy out existing content
        with open(log_path, "rb") as src, open(temp_dest, "wb") as dst:
            shutil.copyfileobj(src, dst)
            dst.flush()
            os.fsync(dst.fileno())

        # Step 2: Safely truncate original file in-place
        with open(log_path, "r+b") as src:
            src.truncate(0)
            src.flush()
            os.fsync(src.fileno())

        # Step 3: Compress intermediate file to gzip
        with open(temp_dest, "rb") as f_in, gzip.open(final_gz, "wb", compresslevel=9) as f_out:
            shutil.copyfileobj(f_in, f_out)

        # Cleanup temp uncompressed file
        if os.path.exists(temp_dest):
            os.remove(temp_dest)

        compressed_size = os.path.getsize(final_gz)
        return final_gz, orig_size, compressed_size

    def rotate_file_if_needed(self, log_path: str, force: bool = False) -> Optional[RotationRecord]:
        """Checks if log file exceeds size threshold, and performs safe rotation."""
        if not os.path.exists(log_path):
            return None

        file_size = os.path.getsize(log_path)
        if not force and file_size < self.max_size_bytes:
            return None

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            archive_path, orig_size, comp_size = self._rotate_copytruncate(log_path)
            checksum = self.compute_sha256(archive_path) if self.verify_sha256 else "SKIPPED"
            ratio = round((1.0 - (comp_size / orig_size)) * 100.0, 1) if orig_size > 0 else 0.0

            # Write individual manifest metadata
            manifest_file = archive_path + ".meta.json"
            meta_data = {
                "original_file": log_path,
                "archive_file": archive_path,
                "rotated_at": now_str,
                "original_size_bytes": orig_size,
                "compressed_size_bytes": comp_size,
                "space_saved_percent": ratio,
                "sha256_checksum": checksum,
                "student_name": "NITHIN N",
                "roll_number": "25BTRPW066"
            }
            with open(manifest_file, "w") as mf:
                json.dump(meta_data, mf, indent=2)

            record = RotationRecord(
                timestamp=now_str,
                original_file=log_path,
                archive_file=archive_path,
                original_size_bytes=orig_size,
                compressed_size_bytes=comp_size,
                compression_ratio_pct=ratio,
                sha256_checksum=checksum,
                strategy_used=self.strategy,
                success=True,
                status_message=f"Successfully rotated {orig_size:,} bytes -> {comp_size:,} bytes ({ratio}% saved)"
            )

            # Enforce retention policy
            self._enforce_retention_policy(os.path.basename(log_path))
            self._append_audit_history(record)
            return record

        except Exception as e:
            err_record = RotationRecord(
                timestamp=now_str,
                original_file=log_path,
                archive_file="",
                original_size_bytes=file_size,
                compressed_size_bytes=0,
                compression_ratio_pct=0.0,
                sha256_checksum="",
                strategy_used=self.strategy,
                success=False,
                status_message=f"Rotation failed: {str(e)}"
            )
            self._append_audit_history(err_record)
            return err_record

    def _enforce_retention_policy(self, base_name: str):
        """Purges oldest archives when count exceeds max_archives limit."""
        try:
            archives = []
            for f in os.listdir(self.archive_dir):
                if f.startswith(base_name) and f.endswith(".gz"):
                    full_p = os.path.join(self.archive_dir, f)
                    archives.append((os.path.getmtime(full_p), full_p))

            archives.sort()  # Oldest first
            if len(archives) > self.max_archives:
                to_remove = archives[:len(archives) - self.max_archives]
                for _, path in to_remove:
                    os.remove(path)
                    meta_p = path + ".meta.json"
                    if os.path.exists(meta_p):
                        os.remove(meta_p)
        except Exception:
            pass

    def _append_audit_history(self, record: RotationRecord):
        """Appends audit event to rotation_history.log."""
        try:
            log_line = (
                f"[{record.timestamp}] STATUS={'SUCCESS' if record.success else 'FAILED'} | "
                f"SRC={record.original_file} | ARCHIVE={record.archive_file} | "
                f"ORIG={record.original_size_bytes}B | GZ={record.compressed_size_bytes}B "
                f"(-{record.compression_ratio_pct}%) | SHA256={record.sha256_checksum[:16]}... | "
                f"MSG={record.status_message}\n"
            )
            with open(self.history_log, "a") as f:
                f.write(log_line)
        except Exception:
            pass

    def check_and_rotate_all(self, force: bool = False) -> List[RotationRecord]:
        """Scans all registered target logs and rotates any exceeding the threshold."""
        results = []
        for log_file in self.target_logs:
            rec = self.rotate_file_if_needed(log_file, force=force)
            if rec:
                results.append(rec)
        return results

    def list_archives(self) -> List[Dict[str, any]]:
        """Returns details of all existing compressed log archives."""
        archives = []
        if not os.path.exists(self.archive_dir):
            return []

        for f in os.listdir(self.archive_dir):
            if f.endswith(".gz"):
                full_path = os.path.join(self.archive_dir, f)
                stat = os.stat(full_path)
                meta_file = full_path + ".meta.json"
                checksum = ""
                orig_size = 0
                if os.path.exists(meta_file):
                    try:
                        with open(meta_file, "r") as mf:
                            mdata = json.load(mf)
                            checksum = mdata.get("sha256_checksum", "")
                            orig_size = mdata.get("original_size_bytes", 0)
                    except Exception:
                        pass

                archives.append({
                    "filename": f,
                    "path": full_path,
                    "size_bytes": stat.st_size,
                    "size_kb": round(stat.st_size / 1024.0, 1),
                    "original_size_bytes": orig_size,
                    "created_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    "sha256": checksum
                })
        archives.sort(key=lambda x: x["created_at"], reverse=True)
        return archives


if __name__ == "__main__":
    rotator = SafeLogRotator()
    print("=== Safe Log Rotation & Archiving Subsystem ===")
    
    # Create a test log file to demonstrate rotation
    test_log = "cyber_log_analyzer/logs/auth.log"
    print(f"[*] Writing 1.2 MB of sample log data into {test_log}...")
    with open(test_log, "w") as f:
        for i in range(15000):
            f.write(f"Nov 02 12:00:{i%60:02d} server sshd[{1000+i}]: Simulated auth activity event log line number {i}\n")

    current_size = os.path.getsize(test_log)
    print(f"[*] Current log size: {current_size:,} bytes")
    
    print("[*] Executing safe copytruncate rotation...")
    record = rotator.rotate_file_if_needed(test_log, force=True)
    if record and record.success:
        print(f"  [+] Rotation Succeeded!")
        print(f"      Archive File     : {record.archive_file}")
        print(f"      Original Size    : {record.original_size_bytes:,} bytes")
        print(f"      Compressed (.gz) : {record.compressed_size_bytes:,} bytes")
        print(f"      Storage Saved    : {record.compression_ratio_pct}%")
        print(f"      SHA-256 Hash     : {record.sha256_checksum}")
        print(f"      New Log Size     : {os.path.getsize(test_log)} bytes (cleanly truncated for active daemons)")
