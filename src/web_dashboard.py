#!/usr/bin/env python3
"""
Cybersecurity & OS Telemetry Web Dashboard (Flask REST API + Interactive UI)
Author: NITHIN N | Roll Number: 25BTRPW066
Provides real-time visualization of CPU/Memory/IO, security incident feeds,
process management controls, and safe log rotation audit explorer.
"""

import os
import sys
import json
import time
import random
import threading
from typing import Optional, List, Dict, Any
from flask import Flask, jsonify, request, render_template_string

# Parent imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.process_monitor import ProcessMonitor, ProcessInfo
from src.memory_monitor import MemoryMonitor
from src.io_monitor import IOMonitor
from src.log_analyzer import LogAnalyzer
from src.log_rotator import SafeLogRotator
from src.alert_manager import AlertManager


def create_app(config_path: Optional[str] = None):
    app = Flask(__name__)

    # Load configuration
    cfg = {}
    if config_path and os.path.exists(config_path):
        with open(config_path, "r") as f:
            cfg = json.load(f)
    else:
        def_path = os.path.join(os.path.dirname(__file__), "../config/default_config.json")
        if os.path.exists(def_path):
            with open(def_path, "r") as f:
                cfg = json.load(f)

    # Detect Vercel / serverless environment (read-only root, writable /tmp)
    is_serverless = os.environ.get("VERCEL") == "1" or not os.access(".", os.W_OK)
    if is_serverless:
        tmp_logs = "/tmp/cyber_logs"
        tmp_archives = "/tmp/cyber_archives"
        os.makedirs(tmp_logs, exist_ok=True)
        os.makedirs(tmp_archives, exist_ok=True)
        if "log_rotation" not in cfg:
            cfg["log_rotation"] = {}
        cfg["log_rotation"]["target_logs"] = [os.path.join(tmp_logs, "auth.log")]
        cfg["log_rotation"]["archive_dir"] = tmp_archives

    # Initialize subsystem engines
    proc_mon = ProcessMonitor(cfg)
    mem_mon = MemoryMonitor(cfg)
    io_mon = IOMonitor(cfg)
    log_ana = LogAnalyzer(cfg)
    rotator = SafeLogRotator(cfg)
    alert_mgr = AlertManager(cfg)

    # Seed initial demo data for Vercel preview
    if is_serverless:
        alert_mgr.record_incident(
            severity="INFO",
            category="SYSTEM_AUDIT",
            title="Cyber Sentinel Online (Cloud Serverless Preview)",
            details="System surveillance daemon initialized. Monitoring virtual telemetry and security audit traces.",
            remediation="Click 'Run Attack Simulation' to test live intrusion detection and copytruncate log rotation."
        )

    # Background monitoring thread (runs in persistent environments)
    def background_monitor_worker():
        while True:
            try:
                sec_alerts = log_ana.scan_all_sources()
                rogues = proc_mon.detect_rogue_processes()
                m_io = io_mon.get_metrics()
                m_mem = mem_mon.get_metrics()
                alert_mgr.correlate_telemetry(sec_alerts, rogues, m_io, m_mem)
                rotator.check_and_rotate_all()
            except Exception:
                pass
            time.sleep(2.0)

    t = threading.Thread(target=background_monitor_worker, daemon=True)
    t.start()

    DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cybersecurity Log Analyzer & OS Monitor | {{ student.name }}</title>
    <style>
        :root {
            --bg: #0b0f19;
            --surface: #111827;
            --card: rgba(17, 24, 39, 0.85);
            --border: #1f2937;
            --text: #e5e7eb;
            --muted: #9ca3af;
            --cyan: #06b6d4;
            --cyan-glow: rgba(6, 182, 212, 0.3);
            --green: #10b981;
            --amber: #f59e0b;
            --red: #ef4444;
            --red-glow: rgba(239, 68, 68, 0.3);
            --purple: #8b5cf6;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; }
        body { background: var(--bg); color: var(--text); padding: 24px; min-height: 100vh; }
        
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 16px; margin-bottom: 24px; }
        .title-group h1 { font-size: 24px; color: #fff; display: flex; align-items: center; gap: 10px; }
        .title-group p { font-size: 13px; color: var(--muted); margin-top: 4px; }
        .badge { background: rgba(6, 182, 212, 0.15); color: var(--cyan); border: 1px solid var(--cyan); padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 600; }
        
        .controls { display: flex; gap: 12px; }
        button { background: #1e293b; color: var(--text); border: 1px solid var(--border); padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 500; transition: all 0.2s; }
        button:hover { background: #334155; }
        button.btn-primary { background: #0284c7; border-color: #38bdf8; color: #fff; }
        button.btn-primary:hover { background: #0369a1; }
        button.btn-danger { background: #b91c1c; border-color: #f87171; color: #fff; }
        button.btn-danger:hover { background: #991b1b; }

        .grid-metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin-bottom: 24px; }
        .card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 18px; backdrop-filter: blur(8px); }
        .card-header { font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); margin-bottom: 8px; display: flex; justify-content: space-between; }
        .card-value { font-size: 32px; font-weight: 700; color: #fff; }
        .card-sub { font-size: 12px; color: var(--muted); margin-top: 6px; }

        .progress-bar { background: #1f2937; height: 6px; border-radius: 3px; overflow: hidden; margin-top: 10px; }
        .progress-fill { height: 100%; border-radius: 3px; transition: width 0.4s ease; }
        .fill-green { background: var(--green); }
        .fill-amber { background: var(--amber); }
        .fill-red { background: var(--red); box-shadow: 0 0 10px var(--red-glow); }

        .main-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        @media (max-width: 1024px) { .main-grid { grid-template-columns: 1fr; } }

        .section-title { font-size: 16px; font-weight: 600; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between; }

        table { width: 100%; border-collapse: collapse; font-size: 13px; }
        th { text-align: left; padding: 10px; color: var(--muted); border-bottom: 1px solid var(--border); font-weight: 500; font-size: 11px; text-transform: uppercase; }
        td { padding: 10px; border-bottom: 1px solid rgba(255,255,255,0.03); color: #d1d5db; }
        tr:hover td { background: rgba(255,255,255,0.02); }

        .alert-item { background: #161e2e; border-left: 4px solid var(--cyan); padding: 12px; border-radius: 4px; margin-bottom: 10px; font-size: 13px; }
        .alert-crit { border-left-color: var(--red); background: rgba(239, 68, 68, 0.08); }
        .alert-warn { border-left-color: var(--amber); background: rgba(245, 158, 11, 0.08); }
        .alert-header { display: flex; justify-content: space-between; font-weight: 600; margin-bottom: 4px; }
        .alert-msg { color: var(--muted); font-size: 12px; }
        .alert-rec { margin-top: 6px; font-size: 11px; color: #38bdf8; }

        .tag-pill { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 10px; font-weight: 600; }
        .pill-red { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #ef4444; }
        .pill-green { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #10b981; }
        .pill-amber { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid #f59e0b; }
    </style>
</head>
<body>

    <div class="header">
        <div class="title-group">
            <h1>🛡️ Cybersecurity Log Analyzer & OS Monitor</h1>
            <p><strong>Student:</strong> {{ student.name }} (Roll: <code>{{ student.roll_number }}</code>) | <strong>Subsystems:</strong> Linux Processes, Memory, Storage I/O, Journalctl, Safe Log Rotation</p>
        </div>
        <div class="controls">
            <button class="btn-primary" onclick="simulateAttack()">⚡ Run Attack Simulation</button>
            <button onclick="triggerRotation()">🔄 Rotate Logs Now</button>
            <span class="badge" id="platform-badge">System: LIVE</span>
        </div>
    </div>

    <!-- Top KPI Cards -->
    <div class="grid-metrics">
        <div class="card">
            <div class="card-header"><span>CPU Load</span><span id="cpu-status" class="tag-pill pill-green">NORMAL</span></div>
            <div class="card-value" id="val-cpu">0.0%</div>
            <div class="progress-bar"><div class="progress-fill fill-green" id="bar-cpu" style="width: 0%"></div></div>
            <div class="card-sub">Core Scheduling & Delta /proc ticks</div>
        </div>
        <div class="card">
            <div class="card-header"><span>Physical RAM</span><span id="mem-status" class="tag-pill pill-green">HEALTHY</span></div>
            <div class="card-value" id="val-mem">0.0%</div>
            <div class="progress-bar"><div class="progress-fill fill-green" id="bar-mem" style="width: 0%"></div></div>
            <div class="card-sub" id="sub-mem">0 MB / 0 MB</div>
        </div>
        <div class="card">
            <div class="card-header"><span>Storage I/O & Wait</span><span id="io-status" class="tag-pill pill-green">LOW WAIT</span></div>
            <div class="card-value" id="val-io">0.0%</div>
            <div class="progress-bar"><div class="progress-fill fill-green" id="bar-io" style="width: 0%"></div></div>
            <div class="card-sub" id="sub-io">Write: 0.0 MB/s | Inodes: 0%</div>
        </div>
        <div class="card">
            <div class="card-header"><span>Active Log Size</span><span class="tag-pill pill-green">COPYTRUNCATE</span></div>
            <div class="card-value" id="val-logsize">0 KB</div>
            <div class="progress-bar"><div class="progress-fill fill-green" id="bar-logsize" style="width: 0%"></div></div>
            <div class="card-sub" id="sub-rot">Limit: 1,024 KB | Archives: 0</div>
        </div>
    </div>

    <!-- Main Grid: Left = Processes, Right = Threats & Archives -->
    <div class="main-grid">
        <!-- Processes Section -->
        <div class="card">
            <div class="section-title">
                <span>Active Process Telemetry (/proc & ps)</span>
                <span style="font-size: 12px; color: var(--muted);">Real-Time Dispatch Table</span>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>PID</th>
                        <th>User</th>
                        <th>Name</th>
                        <th>CPU%</th>
                        <th>RSS (MB)</th>
                        <th>Status</th>
                        <th>Remediation</th>
                    </tr>
                </thead>
                <tbody id="proc-table-body">
                    <tr><td colspan="7">Loading processes...</td></tr>
                </tbody>
            </table>
        </div>

        <!-- Right Side: Cybersecurity Threats & Log Rotations -->
        <div style="display: flex; flex-direction: column; gap: 20px;">
            <!-- Threats -->
            <div class="card">
                <div class="section-title">
                    <span>🚨 Correlated Security Incident Feed</span>
                    <span id="incident-count" class="badge">0 Incidents</span>
                </div>
                <div id="alert-feed-container" style="max-height: 280px; overflow-y: auto;">
                    <p style="color: var(--muted); font-size: 13px;">No threats currently detected. System secure.</p>
                </div>
            </div>

            <!-- Log Rotation & Archives -->
            <div class="card">
                <div class="section-title">
                    <span>📦 Safe Log Rotation & SHA-256 Archive Explorer</span>
                    <button style="padding: 4px 8px; font-size: 11px;" onclick="triggerRotation()">Rotate Now</button>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Archive File</th>
                            <th>Original</th>
                            <th>Compressed (.gz)</th>
                            <th>Saved</th>
                            <th>SHA-256 Hash</th>
                        </tr>
                    </thead>
                    <tbody id="archive-table-body">
                        <tr><td colspan="5">No archives generated yet.</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        async function fetchTelemetry() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                
                // CPU
                document.getElementById('val-cpu').innerText = data.cpu_percent.toFixed(1) + '%';
                const barCpu = document.getElementById('bar-cpu');
                barCpu.style.width = Math.min(100, data.cpu_percent) + '%';
                barCpu.className = 'progress-fill ' + (data.cpu_percent > 80 ? 'fill-red' : data.cpu_percent > 60 ? 'fill-amber' : 'fill-green');
                const badgeCpu = document.getElementById('cpu-status');
                badgeCpu.innerText = data.cpu_percent > 80 ? 'CRITICAL' : data.cpu_percent > 60 ? 'WARNING' : 'NORMAL';
                badgeCpu.className = 'tag-pill ' + (data.cpu_percent > 80 ? 'pill-red' : data.cpu_percent > 60 ? 'pill-amber' : 'pill-green');

                // Memory
                document.getElementById('val-mem').innerText = data.memory.utilization_pct.toFixed(1) + '%';
                const barMem = document.getElementById('bar-mem');
                barMem.style.width = data.memory.utilization_pct + '%';
                barMem.className = 'progress-fill ' + (data.memory.utilization_pct > 85 ? 'fill-red' : data.memory.utilization_pct > 70 ? 'fill-amber' : 'fill-green');
                document.getElementById('sub-mem').innerText = data.memory.used_mb + ' MB / ' + data.memory.total_mb + ' MB';

                // IO
                document.getElementById('val-io').innerText = data.io.iowait_pct.toFixed(1) + '%';
                const barIo = document.getElementById('bar-io');
                barIo.style.width = Math.min(100, data.io.iowait_pct * 2.5) + '%';
                document.getElementById('sub-io').innerText = 'Write: ' + data.io.write_mbs + ' MB/s | Free: ' + data.io.disk_free_gb + ' GB';

                // Log size
                document.getElementById('val-logsize').innerText = (data.log_size_bytes / 1024).toFixed(1) + ' KB';
                const barLog = document.getElementById('bar-logsize');
                const logPct = Math.min(100, (data.log_size_bytes / (1024 * 1024)) * 100);
                barLog.style.width = logPct + '%';
                barLog.className = 'progress-fill ' + (logPct > 90 ? 'fill-red' : 'fill-green');
                document.getElementById('sub-rot').innerText = 'Limit: 1,024 KB | Archives: ' + data.archive_count;

            } catch (e) {
                console.error("Telemetry fetch error:", e);
            }
        }

        async function fetchProcesses() {
            try {
                const res = await fetch('/api/processes');
                const procs = await res.json();
                const tbody = document.getElementById('proc-table-body');
                if (procs.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="7">No processes reported.</td></tr>';
                    return;
                }
                tbody.innerHTML = procs.map(p => `
                    <tr>
                        <td><strong>${p.pid}</strong></td>
                        <td>${p.user}</td>
                        <td><strong>${p.name}</strong></td>
                        <td style="color: ${p.cpu_percent > 60 ? '#f87171' : '#e5e7eb'}">${p.cpu_percent.toFixed(1)}%</td>
                        <td>${p.memory_rss_mb.toFixed(1)}</td>
                        <td><span class="tag-pill ${p.is_suspicious ? 'pill-red' : 'pill-green'}">${p.is_suspicious ? 'SUSPICIOUS' : 'OK'}</span></td>
                        <td>
                            <button style="padding: 2px 6px; font-size: 11px;" onclick="remediate(${p.pid}, 'renice')">Renice</button>
                            <button style="padding: 2px 6px; font-size: 11px;" class="btn-danger" onclick="remediate(${p.pid}, 'sigterm')">Kill</button>
                        </td>
                    </tr>
                `).join('');
            } catch (e) {
                console.error("Process fetch error:", e);
            }
        }

        async function fetchIncidents() {
            try {
                const res = await fetch('/api/alerts');
                const alerts = await res.json();
                const container = document.getElementById('alert-feed-container');
                document.getElementById('incident-count').innerText = alerts.length + ' Incidents';
                if (alerts.length === 0) {
                    container.innerHTML = '<p style="color: var(--muted); font-size: 13px;">No threats currently detected. System secure.</p>';
                    return;
                }
                container.innerHTML = alerts.slice().reverse().map(a => `
                    <div class="alert-item ${a.severity === 'CRITICAL' ? 'alert-crit' : 'alert-warn'}">
                        <div class="alert-header">
                            <span style="color: ${a.severity === 'CRITICAL' ? '#f87171' : '#fbbf24'}">[${a.severity}] ${a.title}</span>
                            <span style="color: var(--muted); font-size: 11px;">${a.timestamp}</span>
                        </div>
                        <div class="alert-msg">${a.details}</div>
                        ${a.remediation_suggestion ? `<div class="alert-rec">💡 <strong>Remediation:</strong> ${a.remediation_suggestion}</div>` : ''}
                    </div>
                `).join('');
            } catch (e) {
                console.error("Incident fetch error:", e);
            }
        }

        async function fetchArchives() {
            try {
                const res = await fetch('/api/archives');
                const archives = await res.json();
                const tbody = document.getElementById('archive-table-body');
                if (archives.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5">No archives generated yet.</td></tr>';
                    return;
                }
                tbody.innerHTML = archives.map(a => `
                    <tr>
                        <td><code>${a.filename}</code></td>
                        <td>${(a.original_size_bytes / 1024).toFixed(1)} KB</td>
                        <td><strong>${a.size_kb} KB</strong></td>
                        <td style="color: #34d399;">-${((1 - (a.size_bytes / Math.max(1, a.original_size_bytes))) * 100).toFixed(0)}%</td>
                        <td><code style="font-size: 11px; color: #06b6d4;">${a.sha256 ? a.sha256.substring(0, 16) + '...' : 'N/A'}</code></td>
                    </tr>
                `).join('');
            } catch (e) {
                console.error("Archive fetch error:", e);
            }
        }

        async function triggerRotation() {
            try {
                const res = await fetch('/api/rotate', { method: 'POST' });
                const data = await res.json();
                alert(data.message || 'Log rotation executed successfully.');
                fetchTelemetry();
                fetchArchives();
            } catch (e) {
                alert('Rotation request failed: ' + e);
            }
        }

        async function remediate(pid, action) {
            try {
                const res = await fetch('/api/remediate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ pid: pid, action: action })
                });
                const data = await res.json();
                alert(data.message);
                fetchProcesses();
            } catch (e) {
                alert('Remediation failed: ' + e);
            }
        }

        async function simulateAttack() {
            try {
                const btn = event.target;
                btn.innerText = '⚡ Injecting Threats...';
                const res = await fetch('/api/simulate', { method: 'POST' });
                const data = await res.json();
                btn.innerText = '⚡ Run Attack Simulation';
                fetchTelemetry();
                fetchProcesses();
                fetchIncidents();
                fetchArchives();
            } catch (e) {
                alert('Simulation failed: ' + e);
            }
        }

        // Live polling loops
        setInterval(fetchTelemetry, 2000);
        setInterval(fetchProcesses, 2500);
        setInterval(fetchIncidents, 3000);
        setInterval(fetchArchives, 5000);

        // Initial fetch
        fetchTelemetry();
        fetchProcesses();
        fetchIncidents();
        fetchArchives();
    </script>
</body>
</html>
    """

    @app.route("/")
    def index():
        student = cfg.get("student_info", {"name": "NITHIN N", "roll_number": "25BTRPW066"})
        return render_template_string(DASHBOARD_HTML, student=student)

    @app.route("/api/status")
    def api_status():
        mem = mem_mon.get_metrics()
        io = io_mon.get_metrics()
        top_p = proc_mon.get_top_processes(n=5)
        
        if is_serverless:
            sec_alerts = log_ana.scan_all_sources()
            rogues = proc_mon.detect_rogue_processes()
            alert_mgr.correlate_telemetry(sec_alerts, rogues, io, mem)
        
        # Calculate aggregate CPU from top processes
        top_cpu = sum(p.cpu_percent for p in top_p)

        target_log = cfg.get("log_rotation", {}).get("target_logs", ["cyber_log_analyzer/logs/auth.log"])[0]
        log_sz = os.path.getsize(target_log) if os.path.exists(target_log) else 0
        archives = rotator.list_archives()

        return jsonify({
            "status": "HEALTHY" if not alert_mgr.incidents else "ALERT",
            "cpu_percent": round(top_cpu, 1),
            "memory": {
                "total_mb": mem.total_mb,
                "used_mb": mem.used_mb,
                "free_mb": mem.free_mb,
                "utilization_pct": mem.utilization_pct
            },
            "io": {
                "read_mbs": io.read_mbs,
                "write_mbs": io.write_mbs,
                "iowait_pct": io.iowait_pct,
                "disk_free_gb": io.disk_free_gb,
                "inodes_used_pct": io.inodes_used_pct
            },
            "log_size_bytes": log_sz,
            "archive_count": len(archives),
            "incident_count": len(alert_mgr.incidents)
        })

    @app.route("/api/processes")
    def api_processes():
        procs = proc_mon.get_top_processes(n=10)
        return jsonify([
            {
                "pid": p.pid,
                "name": p.name,
                "user": p.user,
                "cpu_percent": p.cpu_percent,
                "memory_rss_mb": p.memory_rss_mb,
                "state": p.state,
                "is_suspicious": p.is_suspicious,
                "reasons": p.suspicious_reasons
            }
            for p in procs
        ])

    @app.route("/api/alerts")
    def api_alerts():
        incs = alert_mgr.get_recent_incidents(limit=25)
        return jsonify([
            {
                "incident_id": i.incident_id,
                "timestamp": i.timestamp,
                "severity": i.severity,
                "category": i.category,
                "title": i.title,
                "details": i.details,
                "remediation_suggestion": i.remediation_suggestion
            }
            for i in incs
        ])

    @app.route("/api/archives")
    def api_archives():
        return jsonify(rotator.list_archives())

    @app.route("/api/rotate", methods=["POST"])
    def api_rotate():
        records = rotator.check_and_rotate_all(force=True)
        if records and records[0].success:
            return jsonify({"success": True, "message": records[0].status_message})
        return jsonify({"success": False, "message": "No logs rotated or log file was empty."})

    @app.route("/api/remediate", methods=["POST"])
    def api_remediate():
        data = request.get_json() or {}
        pid = int(data.get("pid", 0))
        action = data.get("action", "renice")
        res = proc_mon.remediate_process(pid, action=action)
        return jsonify(res)

    @app.route("/api/simulate", methods=["POST"])
    def api_simulate():
        """Simulates an end-to-end multi-vector cyber attack."""
        # 1. Inject SSH Brute Force into auth.log
        target_log = cfg.get("log_rotation", {}).get("target_logs", ["cyber_log_analyzer/logs/auth.log"])[0]
        os.makedirs(os.path.dirname(target_log), exist_ok=True)
        attacker_ip = f"192.168.1.{random.randint(180, 220)}"

        with open(target_log, "a") as f:
            for _ in range(5):
                f.write(f"Nov 02 12:45:00 server sshd[9182]: Failed password for invalid user admin from {attacker_ip} port 55102 ssh2\n")
            f.write(f"Nov 02 12:45:05 server sudo: attacker : 3 incorrect password attempts ; TTY=pts/2 ; USER=root ; COMMAND=/bin/bash\n")
            # Pad log to trigger log growth
            for i in range(2000):
                f.write(f"Nov 02 12:45:10 server kernel: [AUDIT_ALERT] Intrusion probe signature logged payload trace index={i}\n")

        # 2. Inject Rogue Process (Cryptominer)
        rogue_pid = random.randint(4000, 4999)
        proc_mon.inject_simulated_process(ProcessInfo(
            pid=rogue_pid,
            ppid=1,
            name="xmrig_miner",
            user="nobody",
            state="R",
            cpu_percent=88.5,
            memory_rss_mb=420.0,
            memory_vsz_mb=980.0,
            memory_percent=5.1,
            cmdline="./xmrig --donate-level 1 -o stratum+tcp://monero.pool:3333 -u 48EDP..",
            is_suspicious=True,
            suspicious_reasons=["Cryptocurrency Mining Pool Traffic Detected", "Excessive CPU usage: 88.5% >= 80.0%"]
        ))

        # 3. Trigger immediate log analysis & correlation
        sec_alerts = log_ana.scan_all_sources()
        rogues = proc_mon.detect_rogue_processes()
        m_io = io_mon.get_metrics()
        m_mem = mem_mon.get_metrics()
        new_incs = alert_mgr.correlate_telemetry(sec_alerts, rogues, m_io, m_mem)

        return jsonify({
            "status": "Attack simulated successfully",
            "attacker_ip": attacker_ip,
            "rogue_pid": rogue_pid,
            "alerts_generated": len(sec_alerts),
            "incidents_created": len(new_incs)
        })

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 8080))
    print(f"[*] Starting Cybersecurity & OS Monitor Dashboard on http://0.0.0.0:{port}...")
    app.run(host="0.0.0.0", port=port, debug=False)
