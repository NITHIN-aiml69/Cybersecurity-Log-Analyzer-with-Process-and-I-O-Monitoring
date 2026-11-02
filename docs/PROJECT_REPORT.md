# ACADEMIC PROJECT REPORT
## Cybersecurity Log Analyzer with Process and I/O Monitoring

**Student Name:** NITHIN N  
**Roll Number:** `25BTRPW066`  
**Course:** Operating Systems Laboratory / Mini Project  
**Course Outcomes:** CO2 (Processes & CPU), CO4 (Memory & Paging), CO5 (Storage & I/O), CO6 (Security & Automation)  
**Tools & Technologies:** Bash, Python 3, Linux `/proc`, `journalctl`, `iostat`, `ps`, `gzip`, `hashlib`  

---

## 1. ABSTRACT & EXECUTIVE SUMMARY

Modern cloud infrastructure and enterprise Linux servers face sophisticated, automated cyber threats ranging from brute-force authentication attacks to stealthy cryptojacking worms and ransomware file-encryption bursts. Conventional Linux utilities monitor system performance in silos—`top` tracks CPU, `free` tracks memory, `iostat` tracks disk throughput, and `fail2ban` monitors log lines—without cross-subsystem correlation.

This project implements **Cyber Sentinel**, an integrated Linux system utility that unifies **kernel performance telemetry** with **cybersecurity threat detection** and **safe automated storage management**. Developed in Python and Bash, the utility operates directly against the Linux `/proc` pseudo-filesystem, systemd `journalctl` streams, and storage subsystem APIs.

Key achievements of the utility include:
1. **Real-time Process & Scheduling Telemetry (CO2):** Directly parses `/proc/[pid]/stat`, computes delta CPU ticks across sampling intervals, identifies rogue/stealth processes (including unlinked binaries and cryptominers), and implements automated OS priority remediation via `os.setpriority` (`renice +19`) and `SIGTERM`.
2. **Memory Management & Paging Diagnostics (CO4):** Inspects physical RAM and virtual memory metrics via `/proc/meminfo`, tracks per-process Resident Set Size (RSS), and monitors dirty writeback page cache to prevent Out-Of-Memory (OOM) killer panics.
3. **Storage I/O & Bottleneck Detection (CO5):** Analyzes disk throughput (MB/s), IOPS, available inodes, and CPU `iowait` from `/proc/diskstats` and `iostat`, identifying ransomware encryption bursts and disk head contention.
4. **Cybersecurity Event Analysis & Multi-Vector Correlation (CO6):** Parses system authentication logs to detect SSH brute-force attacks and sudo privilege escalations using sliding-window rate tracking. Uniquely correlates authentication breaches with subsequent CPU/IO spikes to identify post-compromise exploitation.
5. **Safe Atomic Log Rotation & Archival (CO5, CO6):** Resolves the classic OS file descriptor concurrency hazard using atomic `copytruncate`, compressing rotated logs by over **97%** via `gzip`, and generating **SHA-256** cryptographic hashes for forensic integrity.

---

## 2. THEORETICAL FOUNDATIONS & OPERATING SYSTEM PRINCIPLES

### 2.1 Linux Kernel Pseudo-Filesystem (`/proc`)
The Linux `/proc` directory is not a physical disk filesystem; it is a virtual pseudo-filesystem instantiated in memory by the kernel (VFS). It exposes kernel data structures and Process Control Blocks (PCBs) to user space in human-readable ASCII format.
- `/proc/stat`: Exposes system-wide CPU tick counters (`user`, `nice`, `system`, `idle`, `iowait`, `irq`, `softirq`). Sampling counters at $t_1$ and $t_2$ allows precise calculation of CPU activity:
  $$\text{CPU}_{\text{utilization}} = 100 \times \left( 1 - \frac{\Delta \text{idle} + \Delta \text{iowait}}{\Delta \text{total}} \right)$$
  $$\text{I/O}_{\text{wait}} = 100 \times \frac{\Delta \text{iowait}}{\Delta \text{total}}$$
- `/proc/[pid]/stat`: Contains process scheduling counters including `utime` (user CPU ticks), `stime` (kernel CPU ticks), `vsize` (virtual memory size in bytes), and `rss` (resident set size in physical pages).
- `/proc/[pid]/exe`: A symbolic link pointing to the executed binary on disk. If a malware process deletes its executable after launching to evade signature scanners, Linux appends `(deleted)` to the symlink target—a key heuristic utilized by Cyber Sentinel.
- `/proc/meminfo`: Exposes kernel memory counters including `MemTotal`, `MemFree`, `MemAvailable`, `Buffers`, `Cached`, and `Dirty` (memory awaiting writeback flush to persistent storage).
- `/proc/diskstats`: Exposes block device statistics including reads completed, sectors read, writes completed, sectors written, and time spent doing I/O.

### 2.2 Memory Management & Paging Subsystem (CO4)
Linux employs demand paging with virtual memory addresses mapped to physical page frames via page tables. 
- **Resident Set Size (RSS):** The portion of a process's memory currently resident in physical RAM.
- **Virtual Memory Size (VMS):** The total virtual address space allocated to the process, including mapped shared libraries and swapped pages.
- **Dirty Pages & Writeback:** When a process writes data to a file, the kernel writes to the Page Cache in RAM first (Write-Back Caching). The pages are marked "dirty" until the `flusher` kernel thread flushes them to disk. High dirty page accumulation indicates an I/O bottleneck or disk saturation.

### 2.3 Storage Hierarchy & Disk Scheduling (CO5)
Disk I/O operations are orders of magnitude slower than CPU and RAM accesses. When a process issues a blocking disk read or write request, the kernel transitions the process from `TASK_RUNNING` to `TASK_UNINTERRUPTIBLE` (state `D`). The CPU time spent idling while waiting for outstanding I/O requests is recorded as `iowait`. Persistent `iowait` exceeding 30% indicates disk head contention or storage saturation.

### 2.4 Safe Log Rotation: The Concurrency Problem
When an active daemon (e.g., `rsyslogd`, `sshd`, or `nginx`) runs on a POSIX operating system, it maintains an open file descriptor (`struct file*`) pointing to an inode table entry.
- **Naive Rotation Flaw:** If an administrative script executes `mv logfile logfile.old` or `rm logfile`, the operating system keeps the inode active in memory as long as open file descriptors reference it. The daemon continues writing to the renamed or unlinked inode, causing logs to be lost or hidden from disk tools.
- **Atomic `copytruncate` Solution:**
  1. Open the source log file in read mode and copy all bytes to a temporary archive destination.
  2. Open the source log file in update mode and execute `ftruncate(0)` in-place.
  3. Flush dirty filesystem buffers to physical storage via `os.fsync()`.
  4. The daemon's open file descriptor remains completely valid, and subsequent writes immediately continue at byte offset 0 without dropping records or requiring service restarts.

---

## 3. SUBSYSTEM IMPLEMENTATION DETAILS

### 3.1 Architecture Overview

```
                      +---------------------------------------+
                      |       Cyber Sentinel CLI & GUI        |
                      | (cyber_sentinel.py / web_dashboard.py)|
                      +-------------------+-------------------+
                                          |
        +-------------------+-------------+-------------+-------------------+
        |                   |                           |                   |
        v                   v                           v                   v
+---------------+   +---------------+           +---------------+   +---------------+
|    Process    |   |    Memory     |           |    Storage    |   | Cybersecurity |
|    Monitor    |   |    Monitor    |           |  I/O Monitor  |   | Log Analyzer  |
| (CO2: /proc)  |   | (CO4: meminfo)|           | (CO5: disk)   |   | (CO6: journal)|
+-------+-------+   +-------+-------+           +-------+-------+   +-------+-------+
        |                   |                           |                   |
        +-------------------+-------------+-------------+-------------------+
                                          v
                            +---------------------------+
                            | Incident Correlation Eng. |
                            |    (alert_manager.py)     |
                            +-------------+-------------+
                                          |
                                          v
                            +---------------------------+
                            | Safe Log Rotator & Arch.  |
                            |  (copytruncate + sha256)  |
                            +---------------------------+
```

### 3.2 Subsystem Modules

1. **`process_monitor.py` (CO2):**
   - Directly parses `/proc/[pid]/stat`, `/proc/[pid]/status`, `/proc/[pid]/cmdline`, and `/proc/[pid]/exe`.
   - Computes delta CPU utilization per process using system-wide tick deltas.
   - Flags suspicious processes: CPU usage $\ge 80\%$, RSS $\ge 500\text{ MB}$, unlinked deleted executables, or regex matches against known malware patterns (`xmrig`, `nc -e`, `curl | bash`).
   - Implements automated OS remediation: sets priority nice value to $+19$ (lowest priority) or dispatches `SIGTERM`/`SIGKILL`.

2. **`memory_monitor.py` (CO4):**
   - Extracts `MemTotal`, `MemFree`, `MemAvailable`, `Cached`, and `Dirty` from `/proc/meminfo` (with fallback to `sysctl` and `vm_stat` on macOS).
   - Computes physical memory utilization and tracks dirty page buffer pressure.
   - Emits alerts when RAM utilization exceeds warning (75%) or critical (88%) thresholds.

3. **`io_monitor.py` (CO5):**
   - Monitors `/proc/diskstats` and `iowait` CPU ticks to compute disk read/write throughput (MB/s) and IOPS.
   - Calls `os.statvfs()` to monitor disk space utilization and available inode counts.
   - Detects bulk file write bursts ($\ge 25\text{ MB/s}$) indicative of ransomware or data exfiltration.

4. **`log_analyzer.py` (CO6):**
   - Monitors authentication logs (`auth.log`, `secure`, `system.log`) and systemd `journalctl`.
   - Maintains an incremental file-pointer offset to process newly appended bytes without re-reading past logs.
   - Implements sliding-window rate tracking: flags SSH brute force attacks when $\ge 4$ failed attempts occur within 60 seconds from the same source IP.
   - Flags unauthorized `sudo` executions and dangerous shell command injections.

5. **`alert_manager.py` (Incident Correlation):**
   - Unifies alerts across subsystems.
   - Correlates an authentication breach with an immediate process CPU spike to declare a **Coordinated Cryptojacking Attack**.
   - Correlates authentication failure with high disk write activity to declare a **Potential Ransomware Attack**.

6. **`log_rotator.py` (CO5 & CO6):**
   - Implements atomic `copytruncate` log rotation.
   - Compresses rotated logs using `gzip` format.
   - Computes SHA-256 cryptographic hashes for forensic non-repudiation.
   - Generates `.meta.json` audit manifests and enforces archive retention (keeping at most $N=7$ archives).

7. **`web_dashboard.py` (Presentation & Demonstration):**
   - Built with Flask, featuring live real-time gauges for CPU, Memory, I/O wait, and Log size.
   - Interactive tables for top processes, incident alert feeds, archive explorer, and one-click attack simulation.

---

## 4. EXPERIMENTAL RESULTS & EVALUATION

### 4.1 Automated Attack Simulation Output Trace

Executing `bash cyber_log_analyzer/scripts/simulate_attacks.sh` produces the following experimental output:

```
==============================================================================
      CYBER SENTINEL: AUTOMATED ATTACK & RESOURCE STRESS SIMULATOR
      Student: NITHIN N  |  Roll Number: 25BTRPW066
==============================================================================

[Stage 1/5] Simulating SSH Brute Force Attack from 192.168.1.189...
  [+] Injected failed SSH login attempt #1
  [+] Injected failed SSH login attempt #2
  [+] Injected failed SSH login attempt #3
  [+] Injected failed SSH login attempt #4
  [+] Injected failed SSH login attempt #5

[Stage 2/5] Simulating Privilege Escalation & Command Injection...
  [+] Injected sudo abuse and reverse shell download commands

[Stage 3/5] Simulating I/O Write Storm & Log File Bloat...
  [+] Flooding auth.log with 15,000 transaction traces to breach 1.0MB threshold...
  [✓] Current log file size: 5,045,634 bytes (Exceeds 1,048,576 byte threshold)

[Stage 4/5] Executing Cyber Sentinel Detection Engine...
  [!] 11 Security Threats Detected:
      [CRITICAL] SSH_BRUTE_FORCE_ATTACK | Target: admin@192.168.1.189
          -> SSH Brute Force Detected: 4 failed authentication attempts within 60s from 192.168.1.189
      [WARNING] UNAUTHORIZED_SUDO_ATTEMPT | Target: evil_user@localhost
          -> User 'evil_user' attempted unauthorized sudo execution (not in sudoers)
      [CRITICAL] SUSPICIOUS_PAYLOAD_DETECTED | Target: unknown@system
          -> Unsafe Web Script Piped Directly into Shell: matched pattern 'curl.*\|\s*(?:bash|sh)'

[Stage 5/5] Triggering Safe Atomic Copytruncate Log Rotation...
  [+] Successfully rotated 5,045,634 bytes -> 128,929 bytes (97.4% saved) (SHA-256: b2e13cf45d932267...)

==============================================================================
[✓] ALL ATTACK AND LOG ROTATION TESTS COMPLETED SUCCESSFULLY!
==============================================================================
```

### 4.2 Safe Log Rotation Benchmark

| Metric | Uncompressed Log | Rotated Archive (`.gz`) | Efficiency |
| :--- | :--- | :--- | :--- |
| **File Size** | 5,045,634 bytes (~5.05 MB) | 128,929 bytes (~128 KB) | **97.4% Storage Saved** |
| **Source Log Size Post-Rotation** | 0 bytes (cleanly truncated) | N/A | Zero broken file descriptors |
| **Integrity Hash** | N/A | `b2e13cf45d932267...` | Verified SHA-256 Checksum |
| **Rotation Duration** | N/A | 38 ms | Sub-second execution |

### 4.3 Automated Test Suite Verification

Running `python3 cyber_log_analyzer/tests/test_all.py`:
- `test_co2_process_inspection_and_rogue_detection`: **PASS** (Process table, rogue detection, renice, SIGTERM)
- `test_co4_memory_telemetry`: **PASS** (Physical RAM, cache, dirty buffers)
- `test_co5_storage_io_metrics`: **PASS** (Disk throughput, iowait %, inodes)
- `test_co5_safe_copytruncate_rotation_and_checksum`: **PASS** (Atomic truncation, gzip compression, SHA-256)
- `test_co6_log_analysis_intrusion_signatures`: **PASS** (Sliding-window brute force, sudo escalation, curl|bash)
- `test_correlation_engine`: **PASS** (Auth breach + CPU miner = Coordinated Attack)
- **Result:** 6/6 tests passing in 1.033s (`OK`).

---

## 5. COURSE OUTCOME (CO) ATTAINMENT MATRIX

| Course Outcome | Learning Outcome | Practical Implementation in Project |
| :--- | :--- | :--- |
| **CO2** | Process Scheduling, States, PCB, Priority Management | Reads Linux `/proc/[pid]/stat`, computes delta CPU%, flags rogue processes, implements OS priority remediation via `os.setpriority(nice +19)` and `SIGTERM`. |
| **CO4** | Memory Hierarchy, Paging, Page Buffers & OOM Prevention | Direct inspection of `/proc/meminfo`, physical RAM vs virtual memory tracking, page cache buffers, and dirty page writeback monitoring. |
| **CO5** | File Systems, Storage I/O, Inodes & Atomic Operations | Storage throughput metrics via `/proc/diskstats`, `iowait` CPU analysis, inode utilization via `statvfs`, atomic `copytruncate` log rotation, and `gzip` compression. |
| **CO6** | Security Telemetry, Pattern Matching & Shell Automation | Real-time `journalctl` & `auth.log` monitoring, sliding-window brute-force tracking, suspicious command regex detection, shell automation scripts, and cron scheduling. |

---

## 6. VIVA VOCE DEFENSE & ORAL EXAMINATION CHEAT SHEET

### Q1: What is the `/proc` filesystem in Linux, and how does your project use it?
**Answer:** `/proc` is a virtual pseudo-filesystem created in memory by the Linux kernel. It acts as an interface to kernel data structures and Process Control Blocks (PCBs). Our project parses `/proc/stat` for global CPU ticks and `iowait`, `/proc/meminfo` for memory breakdown, `/proc/diskstats` for storage throughput, and `/proc/[pid]/stat` to compute delta CPU utilization per process.

### Q2: Why is naive log rotation (`mv` or `rm`) dangerous for running daemons?
**Answer:** When a daemon opens a log file, the kernel creates an open file descriptor referencing the file's inode. If `mv` or `rm` is executed, the daemon continues writing to the existing open file descriptor. In the case of `rm`, the file becomes unlinked—its disk blocks remain allocated and consumed, but invisible in `ls`—causing disk exhaustion until the daemon restarts.

### Q3: How does your utility implement safe log rotation?
**Answer:** We implement the **`copytruncate`** pattern:
1. Copy the contents of the active log file to an intermediate archive.
2. In-place truncate the original file using `truncate(0)` without closing or re-opening file descriptors.
3. Call `os.fsync()` to ensure metadata and blocks are committed to physical media.
4. Compress the copy to `.gz` format, compute a SHA-256 hash, and enforce retention limits. The writing process continues appending seamlessly from byte offset 0.

### Q4: How do you calculate process CPU percentage from `/proc`?
**Answer:** We take two samples of `/proc/[pid]/stat` separated by time $\Delta t$. We sum `utime` (user ticks) and `stime` (kernel ticks). The process delta is $\Delta \text{proc} = \text{ticks}_{t_2} - \text{ticks}_{t_1}$. We divide $\Delta \text{proc}$ by the total system CPU tick delta from `/proc/stat` and multiply by $100 \times \text{CPU\_Cores}$.

### Q5: What is `iowait`, and why is it important in cybersecurity?
**Answer:** `iowait` is the percentage of CPU time during which the CPU was idle while there were active, outstanding disk I/O requests. High `iowait` combined with sudden write bursts indicates disk saturation, which in cybersecurity is a primary signature of **ransomware** rapidly reading, encrypting, and re-writing files across the filesystem.

### Q6: How does your log analyzer detect SSH brute force attacks?
**Answer:** It uses regular expressions to parse authentication failure lines (`Failed password for ... from <IP>`). It stores failure timestamps per IP in a sliding time window (e.g., 60 seconds). If an IP accumulates $\ge 4$ failures within the window, a `CRITICAL` alert is triggered, and old timestamps outside the window are automatically pruned.

### Q7: What is the purpose of computing a SHA-256 checksum during log rotation?
**Answer:** In security compliance and digital forensics, log archives must be tamper-evident. Computing a SHA-256 cryptographic hash immediately upon compression provides non-repudiation. Any subsequent unauthorized modification to the compressed log alters the hash, exposing tampering.

### Q8: What does your Incident Correlation Engine do?
**Answer:** Instead of treating security events in isolation, it cross-references log incidents with OS resource telemetry. For example, if an SSH brute-force attack or suspicious `curl | bash` command coincides with a process consuming $\ge 80\%$ CPU, the engine correlates them into a single `COORDINATED_INTRUSION_INCIDENT` (Post-Compromise Cryptojacking).

### Q9: What remediation actions can your utility perform on a rogue process?
**Answer:** It supports **Process De-prioritization (`renice +19`)**, which demotes the process to the lowest scheduling priority queue, preventing CPU starvation for critical services, as well as graceful termination via **`SIGTERM`** and forced termination via **`SIGKILL`**.

### Q10: How does your tool ensure cross-platform compatibility on macOS?
**Answer:** While designed primarily for Linux kernel structures, on macOS/Darwin where `/proc` is absent, the utility detects the POSIX environment and automatically falls back to native commands (`ps`, `sysctl hw.memsize`, `vm_stat`, `statvfs`, and `iostat`), ensuring all features and simulations run seamlessly on macOS as well.
