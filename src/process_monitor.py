#!/usr/bin/env python3
"""
Process and CPU Monitoring Subsystem (CO2: Process Management & CPU Scheduling)
Author: NITHIN N | Roll Number: 25BTRPW066
Watches Linux /proc filesystem (or POSIX ps / simulated process telemetry for Darwin),
computes delta CPU & memory consumption, and detects rogue / suspicious processes.
"""

import os
import sys
import time
import signal
import subprocess
import re
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple


@dataclass
class ProcessInfo:
    pid: int
    ppid: int
    name: str
    user: str
    state: str
    cpu_percent: float
    memory_rss_mb: float
    memory_vsz_mb: float
    memory_percent: float
    cmdline: str
    io_read_bytes: int = 0
    io_write_bytes: int = 0
    exe_deleted: bool = False
    is_suspicious: bool = False
    suspicious_reasons: List[str] = field(default_factory=list)


class ProcessMonitor:
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.thresholds = self.config.get("thresholds", {})
        self.cpu_warn = self.thresholds.get("process_cpu_warning_pct", 60.0)
        self.cpu_crit = self.thresholds.get("process_cpu_critical_pct", 80.0)
        self.mem_warn = self.thresholds.get("process_memory_mb_warning", 500.0)
        self.suspicious_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.config.get(
                "security_rules", {}
            ).get("suspicious_patterns", [
                r"xmrig", r"minerd", r"stratum\+tcp", r"nc\s+-e",
                r"bash\s+-i", r"/dev/tcp/", r"curl.*\|.*bash", r"wget.*\|.*sh"
            ])
        ]
        
        # State tracking for delta CPU calculations
        self._prev_proc_cpu_ticks: Dict[int, int] = {}
        self._prev_system_ticks: int = 0
        self._prev_timestamp: float = time.time()
        self.is_linux = sys.platform.startswith("linux") and os.path.exists("/proc/stat")
        
        # Injected simulated processes (for attack simulation demos)
        self.injected_processes: Dict[int, ProcessInfo] = {}

    def inject_simulated_process(self, proc: ProcessInfo):
        """Allows test runners and simulators to inject live rogue processes for demonstrations."""
        self.injected_processes[proc.pid] = proc

    def remove_simulated_process(self, pid: int):
        if pid in self.injected_processes:
            del self.injected_processes[pid]

    def _read_linux_system_cpu_ticks(self) -> Tuple[int, Dict[str, float]]:
        """Reads /proc/stat to compute total CPU ticks and breakdown."""
        try:
            with open("/proc/stat", "r") as f:
                first_line = f.readline()
            parts = first_line.split()[1:]
            ticks = [int(p) for p in parts]
            total_ticks = sum(ticks)
            
            user = ticks[0] if len(ticks) > 0 else 0
            nice = ticks[1] if len(ticks) > 1 else 0
            system = ticks[2] if len(ticks) > 2 else 0
            idle = ticks[3] if len(ticks) > 3 else 0
            iowait = ticks[4] if len(ticks) > 4 else 0
            
            breakdown = {
                "total": total_ticks,
                "user": user,
                "system": system,
                "idle": idle,
                "iowait": iowait
            }
            return total_ticks, breakdown
        except Exception:
            return 0, {}

    def _read_linux_proc_pid(self, pid: int, total_sys_ticks: int, delta_sys_ticks: int) -> Optional[ProcessInfo]:
        """Parses /proc/[pid]/stat, status, cmdline, exe, and io on Linux."""
        proc_dir = f"/proc/{pid}"
        if not os.path.exists(proc_dir):
            return None

        try:
            with open(f"{proc_dir}/stat", "r") as f:
                stat_content = f.read()
            
            rparen = stat_content.rfind(")")
            lparen = stat_content.find("(")
            if lparen == -1 or rparen == -1:
                return None
            
            comm = stat_content[lparen + 1:rparen]
            rest = stat_content[rparen + 2:].split()
            state = rest[0]
            ppid = int(rest[1])
            utime = int(rest[11])
            stime = int(rest[12])
            vsize = int(rest[20])
            rss_pages = int(rest[21])
            
            page_size = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096
            rss_mb = (rss_pages * page_size) / (1024 * 1024)
            vsz_mb = vsize / (1024 * 1024)
            
            proc_ticks = utime + stime
            prev_ticks = self._prev_proc_cpu_ticks.get(pid, proc_ticks)
            delta_proc = max(0, proc_ticks - prev_ticks)
            self._prev_proc_cpu_ticks[pid] = proc_ticks

            cpu_pct = 0.0
            if delta_sys_ticks > 0:
                cpu_count = os.cpu_count() or 1
                cpu_pct = min(100.0 * cpu_count, (delta_proc / delta_sys_ticks) * 100.0 * cpu_count)

            cmdline = comm
            try:
                with open(f"{proc_dir}/cmdline", "rb") as f:
                    raw_cmd = f.read()
                    if raw_cmd:
                        cmdline = raw_cmd.replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()
            except Exception:
                pass

            user = str(pid)
            try:
                with open(f"{proc_dir}/status", "r") as f:
                    for line in f:
                        if line.startswith("Uid:"):
                            uid = int(line.split()[1])
                            import pwd
                            try:
                                user = pwd.getpwuid(uid).pw_name
                            except Exception:
                                user = str(uid)
                            break
            except Exception:
                pass

            exe_deleted = False
            try:
                exe_target = os.readlink(f"{proc_dir}/exe")
                if "(deleted)" in exe_target:
                    exe_deleted = True
            except Exception:
                pass

            read_bytes, write_bytes = 0, 0
            try:
                with open(f"{proc_dir}/io", "r") as f:
                    for line in f:
                        if line.startswith("read_bytes:"):
                            read_bytes = int(line.split()[1])
                        elif line.startswith("write_bytes:"):
                            write_bytes = int(line.split()[1])
            except Exception:
                pass

            suspicious_reasons = []
            if exe_deleted:
                suspicious_reasons.append("Executable unlinked from filesystem (stealth binary)")
            if cpu_pct >= self.cpu_crit:
                suspicious_reasons.append(f"Excessive CPU usage: {cpu_pct:.1f}% >= {self.cpu_crit:.1f}%")
            if rss_mb >= self.mem_warn:
                suspicious_reasons.append(f"Excessive RSS memory: {rss_mb:.1f}MB >= {self.mem_warn:.1f}MB")
            
            for pat in self.suspicious_patterns:
                if pat.search(cmdline) or pat.search(comm):
                    suspicious_reasons.append(f"Suspicious signature matched: {pat.pattern}")
                    break

            is_suspicious = len(suspicious_reasons) > 0

            return ProcessInfo(
                pid=pid,
                ppid=ppid,
                name=comm,
                user=user,
                state=state,
                cpu_percent=round(cpu_pct, 1),
                memory_rss_mb=round(rss_mb, 1),
                memory_vsz_mb=round(vsz_mb, 1),
                memory_percent=round((rss_mb / 16384.0) * 100, 1),
                cmdline=cmdline,
                io_read_bytes=read_bytes,
                io_write_bytes=write_bytes,
                exe_deleted=exe_deleted,
                is_suspicious=is_suspicious,
                suspicious_reasons=suspicious_reasons
            )
        except Exception:
            return None

    def _get_processes_linux(self) -> List[ProcessInfo]:
        """Linux /proc scanning method."""
        cur_ticks, _ = self._read_linux_system_cpu_ticks()
        delta_sys_ticks = cur_ticks - self._prev_system_ticks if self._prev_system_ticks else 0
        self._prev_system_ticks = cur_ticks

        processes = []
        try:
            pids = [int(p) for p in os.listdir("/proc") if p.isdigit()]
        except Exception:
            return []

        for pid in pids:
            info = self._read_linux_proc_pid(pid, cur_ticks, delta_sys_ticks)
            if info:
                processes.append(info)
        return processes

    def _get_processes_posix_ps(self) -> List[ProcessInfo]:
        """POSIX ps fallback."""
        processes = []
        try:
            cmd = ["ps", "-axo", "pid,ppid,user,%cpu,%mem,vsz,rss,state,comm,command"]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=2)
            if proc.returncode == 0:
                lines = proc.stdout.strip().split("\n")
                for line in lines[1:]:
                    parts = line.split(None, 9)
                    if len(parts) < 10:
                        continue
                    pid = int(parts[0])
                    ppid = int(parts[1])
                    user = parts[2]
                    cpu_pct = float(parts[3])
                    mem_pct = float(parts[4])
                    vsz_kb = float(parts[5])
                    rss_kb = float(parts[6])
                    state = parts[7]
                    comm = parts[8]
                    cmdline = parts[9]

                    rss_mb = round(rss_kb / 1024.0, 1)
                    vsz_mb = round(vsz_kb / 1024.0, 1)

                    suspicious_reasons = []
                    if cpu_pct >= self.cpu_crit:
                        suspicious_reasons.append(f"Excessive CPU usage: {cpu_pct:.1f}% >= {self.cpu_crit:.1f}%")
                    if rss_mb >= self.mem_warn:
                        suspicious_reasons.append(f"Excessive RSS memory: {rss_mb:.1f}MB >= {self.mem_warn:.1f}MB")

                    for pat in self.suspicious_patterns:
                        if pat.search(cmdline) or pat.search(comm):
                            suspicious_reasons.append(f"Suspicious signature matched: {pat.pattern}")
                            break

                    processes.append(ProcessInfo(
                        pid=pid,
                        ppid=ppid,
                        name=os.path.basename(comm),
                        user=user,
                        state=state,
                        cpu_percent=cpu_pct,
                        memory_rss_mb=rss_mb,
                        memory_vsz_mb=vsz_mb,
                        memory_percent=mem_pct,
                        cmdline=cmdline,
                        exe_deleted=False,
                        is_suspicious=len(suspicious_reasons) > 0,
                        suspicious_reasons=suspicious_reasons
                    ))
        except Exception:
            pass
        return processes

    def _get_simulated_process_table(self) -> List[ProcessInfo]:
        """
        Generates realistic OS process table telemetry for macOS/sandbox testing,
        demonstrating core OS states (Running, Sleeping, Disk Sleep, Zombie),
        CPU distribution, and I/O rates.
        """
        base_templates = [
            (1, 0, "systemd", "root", "S", 0.1, 48.2, 160.0, "/sbin/init"),
            (114, 1, "systemd-journald", "root", "S", 0.4, 62.5, 210.0, "/lib/systemd/systemd-journald"),
            (245, 1, "rsyslogd", "syslog", "S", 0.2, 28.1, 95.0, "/usr/sbin/rsyslogd -n -iNONE"),
            (389, 1, "sshd", "root", "S", 0.3, 34.0, 120.0, "sshd: /usr/sbin/sshd -D"),
            (512, 1, "nginx", "www-data", "S", 3.2, 112.4, 450.0, "nginx: worker process"),
            (620, 1, "mysqld", "mysql", "S", 5.8, 380.0, 1200.0, "/usr/sbin/mysqld --daemonize"),
            (701, 1, "cron", "root", "S", 0.0, 14.2, 45.0, "/usr/sbin/cron -f"),
            (820, 389, "sshd_session", "nithin", "S", 0.5, 22.4, 85.0, "sshd: nithin@pts/0"),
            (950, 820, "bash", "nithin", "S", 0.1, 18.2, 60.0, "/bin/bash"),
            (1044, 950, "python3", "nithin", "R", 1.8, 45.0, 180.0, "python3 cyber_sentinel.py monitor"),
            (1120, 1, "kworker/u8:2", "root", "I", 0.1, 0.0, 0.0, "[kworker/u8:2-events_unbound]")
        ]

        procs = []
        for pid, ppid, name, user, state, cpu, mem_rss, mem_vsz, cmdline in base_templates:
            # Slight dynamic jitter for realistic live updates
            jitter_cpu = max(0.0, round(cpu + random.uniform(-0.1, 0.3), 1))
            jitter_mem = max(5.0, round(mem_rss + random.uniform(-1.0, 1.5), 1))
            procs.append(ProcessInfo(
                pid=pid,
                ppid=ppid,
                name=name,
                user=user,
                state=state,
                cpu_percent=jitter_cpu,
                memory_rss_mb=jitter_mem,
                memory_vsz_mb=mem_vsz,
                memory_percent=round((jitter_mem / 8192.0) * 100, 1),
                cmdline=cmdline,
                io_read_bytes=int(jitter_cpu * 1024 * 50),
                io_write_bytes=int(jitter_cpu * 1024 * 20),
                exe_deleted=False,
                is_suspicious=False,
                suspicious_reasons=[]
            ))
        return procs

    def get_all_processes(self) -> List[ProcessInfo]:
        """Returns snapshot of running processes across platforms."""
        procs = []
        if self.is_linux:
            procs = self._get_processes_linux()
        
        if not procs:
            procs = self._get_processes_posix_ps()

        if not procs:
            procs = self._get_simulated_process_table()

        # Merge any dynamically injected rogue processes
        for pid, inj in list(self.injected_processes.items()):
            procs = [p for p in procs if p.pid != pid]
            procs.append(inj)

        return procs

    def get_top_processes(self, n: int = 10, sort_by: str = "cpu") -> List[ProcessInfo]:
        """Retrieves top N processes sorted by cpu or memory."""
        all_procs = self.get_all_processes()
        if sort_by == "memory":
            all_procs.sort(key=lambda p: p.memory_rss_mb, reverse=True)
        else:
            all_procs.sort(key=lambda p: p.cpu_percent, reverse=True)
        return all_procs[:n]

    def detect_rogue_processes(self) -> List[ProcessInfo]:
        """Scans for processes triggering CPU, memory, or security flags."""
        all_procs = self.get_all_processes()
        rogues = []
        for p in all_procs:
            reasons = list(p.suspicious_reasons)
            if p.cpu_percent >= self.cpu_crit and not any("Excessive CPU" in r for r in reasons):
                reasons.append(f"Excessive CPU usage: {p.cpu_percent:.1f}% >= {self.cpu_crit:.1f}%")
            if p.memory_rss_mb >= self.mem_warn and not any("Excessive RSS" in r for r in reasons):
                reasons.append(f"Excessive RSS memory: {p.memory_rss_mb:.1f}MB >= {self.mem_warn:.1f}MB")
            for pat in self.suspicious_patterns:
                if (pat.search(p.cmdline) or pat.search(p.name)) and not any(pat.pattern in r for r in reasons):
                    reasons.append(f"Suspicious signature matched: {pat.pattern}")
                    break
            if reasons:
                p.is_suspicious = True
                p.suspicious_reasons = reasons
                rogues.append(p)
        return rogues

    def remediate_process(self, pid: int, action: str = "renice", nice_val: int = 19) -> Dict[str, any]:
        """Remediates a rogue process via OS scheduling signals or priority de-escalation."""
        result = {"pid": pid, "action": action, "success": False, "message": ""}
        if pid in self.injected_processes:
            if action in ["sigterm", "sigkill"]:
                del self.injected_processes[pid]
                result["success"] = True
                result["message"] = f"Terminated simulated rogue process PID {pid} via {action.upper()}"
                return result
            elif action == "renice":
                self.injected_processes[pid].cpu_percent = max(1.0, self.injected_processes[pid].cpu_percent * 0.2)
                result["success"] = True
                result["message"] = f"De-prioritized simulated PID {pid} to nice {nice_val} (throttled CPU)"
                return result

        try:
            if action == "renice":
                if hasattr(os, "setpriority") and hasattr(os, "PRIO_PROCESS"):
                    os.setpriority(os.PRIO_PROCESS, pid, nice_val)
                    result["success"] = True
                    result["message"] = f"Successfully set nice priority of PID {pid} to {nice_val}"
                else:
                    cmd = ["renice", str(nice_val), "-p", str(pid)]
                    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    result["success"] = True
                    result["message"] = f"Executed renice {nice_val} for PID {pid}"
            elif action == "sigterm":
                os.kill(pid, signal.SIGTERM)
                result["success"] = True
                result["message"] = f"Dispatched SIGTERM to PID {pid}"
            elif action == "sigkill":
                os.kill(pid, signal.SIGKILL)
                result["success"] = True
                result["message"] = f"Dispatched SIGKILL to PID {pid}"
            else:
                result["message"] = f"Unknown remediation action: {action}"
        except ProcessLookupError:
            result["message"] = f"Process {pid} no longer exists."
        except PermissionError:
            result["message"] = f"Permission denied to remediate PID {pid} (requires root privileges)."
        except Exception as e:
            result["message"] = f"Error during remediation: {str(e)}"

        return result


if __name__ == "__main__":
    pm = ProcessMonitor()
    print(f"[*] Scanning processes (Platform: {'Linux /proc' if pm.is_linux else 'Cross-Platform/Simulated'})...")
    top_cpu = pm.get_top_processes(n=5, sort_by="cpu")
    print(f"{'PID':<8} {'USER':<12} {'CPU%':<8} {'MEM(MB)':<10} {'NAME':<20} {'CMD'}")
    print("-" * 75)
    for p in top_cpu:
        print(f"{p.pid:<8} {p.user:<12} {p.cpu_percent:<8.1f} {p.memory_rss_mb:<10.1f} {p.name:<20} {p.cmdline[:30]}")
    
    rogues = pm.detect_rogue_processes()
    print(f"\n[*] Rogue / Suspicious Processes Detected: {len(rogues)}")
