"""
Thermospatial Occupancy and Caloric Telemetry System (TOCTS)
============================================================
An academic-grade telemetry ingestion, processing, and visualization suite
designed to quantify and graph physical workspace chair occupancy.

Author: Engineering Operations
License: Proprietary / Corporate Compliance
"""

import asyncio
import json
import math
import os
import random
import sqlite3
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# Initialize FastAPI application
app = FastAPI(
    title="Thermospatial Occupancy & Caloric Telemetry System (TOCTS)",
    description="Quantitative seat-pan presence compliance telemetry ingestion and analysis.",
    version="1.0.0"
)

DB_PATH = "telemetry.db"
SENSOR_ID = "chair_evt_01"

# -------------------------------------------------------------------------
# DATABASE INITIALIZATION
# -------------------------------------------------------------------------

def initialize_database():
    """
    Initializes the SQLite database with appropriate indices for time-series extraction.
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chair_telemetry (
                timestamp INTEGER PRIMARY KEY,
                sensor_id TEXT NOT NULL,
                chair_temp REAL NOT NULL,
                ambient_temp REAL NOT NULL,
                delta_temp REAL NOT NULL,
                occupied INTEGER NOT NULL
            )
        """)
        # Index on timestamp to accelerate polling queries
        conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON chair_telemetry (timestamp)")
        conn.commit()

initialize_database()

# -------------------------------------------------------------------------
# SIMULATION STATE & PHYSICS ENGINE
# -------------------------------------------------------------------------

class PhysicalState:
    """
    Represents the simulated physical environment.
    Uses basic thermodynamic heat transfer formulas to simulate seat heating and cooling.
    """
    def __init__(self):
        self.is_sitting = False
        self.ambient_temp = 22.0  # Baseline room temperature
        self.chair_temp = 22.0    # Starts at room temperature
        self.target_body_temp = 37.0  # Human core temperature
        
        # Thermal resistance/capacity coefficients
        self.k_heating = 0.05  # Logarithmic rise rate when occupied
        self.k_cooling = 0.03  # Exponential decay rate when vacant
        
        # Simulated cumulative metrics (in seconds)
        self.cumulative_occupied_time = 18000.0  # Starts with 5.0 hours of simulated baseline presence
        self.last_update = time.time()

state = PhysicalState()

async def thermodynamic_simulation_loop():
    """
    Background worker simulating temperature changes based on physical actions.
    Updates the environment every 1.0 seconds and commits telemetry logs to SQLite.
    """
    while True:
        try:
            now = time.time()
            dt = now - state.last_update
            state.last_update = now
            
            # Heat transfer math: dT/dt = -k * (T - T_target)
            if state.is_sitting:
                # Logarithmic heating curve towards body temperature (37 C)
                # Adds minor metabolic jitter
                jitter = random.uniform(-0.05, 0.05)
                state.chair_temp += state.k_heating * (state.target_body_temp - state.chair_temp) * dt + (jitter * dt)
                state.cumulative_occupied_time += dt
            else:
                # Exponential cooling curve towards ambient temperature
                jitter = random.uniform(-0.02, 0.02)
                state.chair_temp += state.k_cooling * (state.ambient_temp - state.chair_temp) * dt + (jitter * dt)
            
            # Constrain physical limits
            state.chair_temp = max(state.ambient_temp - 2.0, min(state.chair_temp, state.target_body_temp + 0.5))
            
            # Compute differential calculus delta
            delta_t = state.chair_temp - state.ambient_temp
            # Occupancy classification boundary (Delta T >= 2.5 C)
            is_occupied = 1 if delta_t >= 2.5 else 0
            
            # Commit record to local SQLite instance
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO chair_telemetry VALUES (?, ?, ?, ?, ?, ?)",
                    (int(now), SENSOR_ID, round(state.chair_temp, 2), round(state.ambient_temp, 2), round(delta_t, 2), is_occupied)
                )
                conn.commit()
                
        except Exception as e:
            print(f"[SIMULATOR ERROR] {e}")
            
        await asyncio.sleep(1.0)

# Start background simulator task on application startup
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(thermodynamic_simulation_loop())

# -------------------------------------------------------------------------
# API DATA SCHEMAS
# -------------------------------------------------------------------------

class TelemetryPayload(BaseModel):
    sensor_id: str
    chair_temp: float
    ambient_temp: float

class OverrideState(BaseModel):
    is_sitting: bool

class AdjustAmbient(BaseModel):
    ambient_temp: float

# -------------------------------------------------------------------------
# HTTP REST ENDPOINTS
# -------------------------------------------------------------------------

@app.post("/telemetry")
async def ingest_telemetry(payload: TelemetryPayload):
    """
    Endpoint for external hardware (ESP32) to ingest RAW telemetry.
    Overrides internal simulation variables when external data arrives.
    """
    now = int(time.time())
    delta_t = payload.chair_temp - payload.ambient_temp
    is_occupied = 1 if delta_t >= 2.5 else 0
    
    # Sync internal simulator state with real hardware packet
    state.chair_temp = payload.chair_temp
    state.ambient_temp = payload.ambient_temp
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO chair_telemetry VALUES (?, ?, ?, ?, ?, ?)",
            (now, payload.sensor_id, payload.chair_temp, payload.ambient_temp, round(delta_t, 2), is_occupied)
        )
        conn.commit()
    return {"status": "success", "timestamp": now}

@app.get("/api/history")
async def get_history(limit: int = 100):
    """
    Retrieves the chronological window of telemetry points to plot in Chart.js.
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        # Retrieve latest points ordered by timestamp ascending for plotting
        cursor.execute(
            "SELECT * FROM (SELECT * FROM chair_telemetry ORDER BY timestamp DESC LIMIT ?) ORDER BY timestamp ASC",
            (limit,)
        )
        rows = cursor.fetchall()
        
    return [dict(row) for row in rows]

@app.get("/api/summary")
async def get_summary():
    """
    Calculates instant KPIs, cumulative occupation hours, and target compliance percentage.
    """
    delta_t = state.chair_temp - state.ambient_temp
    is_occupied = delta_t >= 2.5
    
    # Calculate compliance target (8.0 Hours Target = 28800 seconds)
    target_seconds = 28800.0
    compliance_percent = min(100.0, (state.cumulative_occupied_time / target_seconds) * 100.0)
    
    return {
        "sensor_id": SENSOR_ID,
        "chair_temp": round(state.chair_temp, 2),
        "ambient_temp": round(state.ambient_temp, 2),
        "delta_temp": round(delta_t, 2),
        "is_occupied": is_occupied,
        "cumulative_hours": round(state.cumulative_occupied_time / 3600.0, 2),
        "compliance_percentage": round(compliance_percent, 1)
    }

@app.post("/api/simulate/state")
async def set_simulate_state(payload: OverrideState):
    """
    Switches simulation physical state (Sitting vs Vacant).
    """
    state.is_sitting = payload.is_sitting
    return {"status": "state updated", "is_sitting": state.is_sitting}

@app.post("/api/simulate/ambient")
async def set_simulate_ambient(payload: AdjustAmbient):
    """
    Allows adjustment of ambient temperature to test HVAC differential compensations.
    """
    state.ambient_temp = payload.ambient_temp
    return {"status": "ambient updated", "ambient_temp": state.ambient_temp}

@app.post("/api/purge")
async def purge_database():
    """
    Clears all database history and resets cumulative statistics.
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM chair_telemetry")
        conn.commit()
    state.cumulative_occupied_time = 0.0
    state.chair_temp = state.ambient_temp
    state.is_sitting = False
    return {"status": "database purged"}

@app.get("/metrics")
async def prometheus_metrics():
    """
    Prometheus text exposition scraping output.
    """
    delta_t = state.chair_temp - state.ambient_temp
    occupied_val = 1 if delta_t >= 2.5 else 0
    
    metrics = [
        f'# HELP chair_temperature_celsius Instantaneous seat-pan temperature in Celsius',
        f'# TYPE chair_temperature_celsius gauge',
        f'chair_temperature_celsius{{sensor_id="{SENSOR_ID}"}} {round(state.chair_temp, 2)}',
        f'# HELP ambient_temperature_celsius Instantaneous ambient desk temperature in Celsius',
        f'# TYPE ambient_temperature_celsius gauge',
        f'ambient_temperature_celsius{{sensor_id="{SENSOR_ID}"}} {round(state.ambient_temp, 2)}',
        f'# HELP seat_occupancy_status Binary classification of physical workspace presence (1=Occupied, 0=Vacant)',
        f'# TYPE seat_occupancy_status gauge',
        f'seat_occupancy_status{{sensor_id="{SENSOR_ID}"}} {occupied_val}',
        f'# HELP cumulative_presence_hours Total logged seat-warmth compliance hours',
        f'# TYPE cumulative_presence_hours counter',
        f'cumulative_presence_hours{{sensor_id="{SENSOR_ID}"}} {round(state.cumulative_occupied_time / 3600.0, 4)}'
    ]
    return HTMLResponse(content="\n".join(metrics) + "\n", media_type="text/plain")

# -------------------------------------------------------------------------
# INTERACTIVE SINGLE-PAGE HTML/CSS/JS INTERFACE
# -------------------------------------------------------------------------

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TOCTS // Live Control Center</title>
    <!-- Chart.js and Font Selection -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-base: #0d1117;
            --bg-surface: #161b22;
            --bg-card: #21262d;
            --border-muted: #30363d;
            --text-primary: #c9d1d9;
            --text-secondary: #8b949e;
            --neon-green: #2ecc71;
            --neon-blue: #00bfff;
            --neon-orange: #ff6600;
            --neon-red: #ff3333;
            --glow-green: 0 0 10px rgba(46, 204, 113, 0.4);
            --glow-orange: 0 0 10px rgba(255, 102, 0, 0.4);
            --glow-blue: 0 0 10px rgba(0, 191, 255, 0.4);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background-color: var(--bg-base);
            color: var(--text-primary);
            font-family: 'JetBrains Mono', monospace;
            padding: 24px;
            font-size: 14px;
            line-height: 1.5;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid var(--border-muted);
            padding-bottom: 16px;
            margin-bottom: 24px;
        }

        .title-area h1 {
            font-size: 20px;
            font-weight: 700;
            letter-spacing: -0.5px;
            color: #ffffff;
        }

        .title-area p {
            color: var(--text-secondary);
            font-size: 11px;
            text-transform: uppercase;
            margin-top: 4px;
        }

        .system-status {
            display: flex;
            align-items: center;
            gap: 8px;
            background: var(--bg-surface);
            border: 1px solid var(--border-muted);
            padding: 6px 12px;
            border-radius: 4px;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            background-color: var(--neon-green);
            border-radius: 50%;
            box-shadow: var(--glow-green);
            animation: pulse 1.5s infinite alternate;
        }

        @keyframes pulse {
            0% { transform: scale(1); opacity: 0.6; }
            100% { transform: scale(1.2); opacity: 1; }
        }

        .grid-layout {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin-bottom: 24px;
        }

        .card {
            background-color: var(--bg-surface);
            border: 1px solid var(--border-muted);
            border-radius: 6px;
            padding: 20px;
            position: relative;
            overflow: hidden;
        }

        .card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 2px;
            background: var(--border-muted);
        }

        .card.active-presence::before {
            background: linear-gradient(90deg, var(--neon-orange), var(--neon-red));
        }

        .card.ambient-card::before {
            background: var(--neon-blue);
        }

        .card.compliance-card::before {
            background: var(--neon-green);
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            color: var(--text-secondary);
            font-size: 11px;
            text-transform: uppercase;
            margin-bottom: 12px;
        }

        .card-value {
            font-size: 32px;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 4px;
        }

        .card-subtext {
            font-size: 11px;
            color: var(--text-secondary);
        }

        /* Large Chart Section */
        .chart-section {
            grid-column: span 2;
            background-color: var(--bg-surface);
            border: 1px solid var(--border-muted);
            border-radius: 6px;
            padding: 20px;
        }

        /* Controls Panel */
        .controls-section {
            background-color: var(--bg-surface);
            border: 1px solid var(--border-muted);
            border-radius: 6px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        .control-group {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .control-group label {
            font-size: 11px;
            text-transform: uppercase;
            color: var(--text-secondary);
        }

        .btn-toggle-group {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
        }

        button {
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            background-color: var(--bg-card);
            color: var(--text-primary);
            border: 1px solid var(--border-muted);
            padding: 10px 14px;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.2s ease;
            text-transform: uppercase;
            font-weight: bold;
        }

        button:hover {
            border-color: var(--text-primary);
            background-color: #30363d;
        }

        button.active {
            background-color: var(--neon-orange);
            color: #000000;
            border-color: var(--neon-orange);
            box-shadow: var(--glow-orange);
        }

        button.active-alt {
            background-color: var(--neon-blue);
            color: #000000;
            border-color: var(--neon-blue);
            box-shadow: var(--glow-blue);
        }

        .range-slider {
            width: 100%;
            height: 6px;
            background: var(--border-muted);
            outline: none;
            border-radius: 3px;
            -webkit-appearance: none;
            margin: 8px 0;
        }

        .range-slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background: var(--neon-blue);
            cursor: pointer;
            box-shadow: var(--glow-blue);
        }

        /* Terminal Console */
        .terminal-section {
            grid-column: span 3;
            background-color: #05080c;
            border: 1px solid var(--border-muted);
            border-radius: 6px;
            padding: 16px;
            height: 180px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .terminal-header {
            display: flex;
            justify-content: space-between;
            color: var(--text-secondary);
            font-size: 11px;
            text-transform: uppercase;
            border-bottom: 1px solid var(--border-muted);
            padding-bottom: 6px;
        }

        .terminal-logs {
            overflow-y: auto;
            flex-grow: 1;
            font-size: 12px;
            color: var(--neon-green);
            display: flex;
            flex-direction: column-reverse;
            gap: 4px;
            scroll-behavior: smooth;
        }

        .terminal-line {
            line-height: 1.4;
        }

        .timestamp-log {
            color: var(--text-secondary);
        }

        .accent-log {
            color: var(--neon-blue);
        }

        .progress-ring-container {
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
        }

        /* Responsive */
        @media (max-width: 900px) {
            .grid-layout {
                grid-template-columns: 1fr;
            }
            .chart-section {
                grid-column: span 1;
            }
            .terminal-section {
                grid-column: span 1;
            }
        }
    </style>
</head>
<body>

    <header>
        <div class="title-area">
            <h1>TOCTS // CONTROL & TELEMETRY TERMINAL</h1>
            <p>Thermographic presence validation interface // Spoofed: HP-LaserJet-M404dn</p>
        </div>
        <div class="system-status">
            <div class="status-dot"></div>
            <span style="font-size: 11px; font-weight: bold; text-transform: uppercase;">Node: ACTIVE</span>
        </div>
    </header>

    <div class="grid-layout">
        <!-- Card 1: Occupancy State -->
        <div id="occupancyCard" class="card">
            <div class="card-header">
                <span>Occupancy Vector</span>
                <span id="badgeText">CALIBRATING</span>
            </div>
            <div id="occupancyVal" class="card-value" style="color: var(--text-secondary);">VACANT</div>
            <div id="occupancySub" class="card-subtext">Seat-pan delta standard is inactive</div>
        </div>

        <!-- Card 2: Thermal Delta -->
        <div class="card ambient-card">
            <div class="card-header">
                <span>Thermal Diagnostics</span>
                <span>Delta (ΔT)</span>
            </div>
            <div id="deltaVal" class="card-value" style="color: var(--neon-blue);">0.00°C</div>
            <div class="card-subtext" id="tempDeets">Seat: --°C // Ambient: --°C</div>
        </div>

        <!-- Card 3: Compliance Metrics -->
        <div class="card compliance-card">
            <div class="card-header">
                <span>Audit Validation Status</span>
                <span>Target: 8.0 hrs</span>
            </div>
            <div id="complianceVal" class="card-value" style="color: var(--neon-green);">0%</div>
            <div id="cumulativeVal" class="card-subtext">Elapsed presence: 0.00 hours</div>
        </div>
    </div>

    <div class="grid-layout">
        <!-- Interactive Chart -->
        <div class="chart-section">
            <div class="card-header" style="margin-bottom: 16px;">
                <span>Time-Series Thermographic Record</span>
                <span>Live polling (1000ms)</span>
            </div>
            <div style="height: 300px; position: relative;">
                <canvas id="telemetryChart"></canvas>
            </div>
        </div>

        <!-- Local Controls Panel -->
        <div class="controls-section">
            <div class="card-header" style="border-bottom: 1px solid var(--border-muted); padding-bottom: 8px;">
                <span>Hardware Simulator Controls</span>
            </div>
            
            <div class="control-group">
                <label>Physical Presence Vector</label>
                <div class="btn-toggle-group">
                    <button id="btnVacant" class="active" onclick="setPresence(false)">Vacant</button>
                    <button id="btnSitting" onclick="setPresence(true)">Sitting</button>
                </div>
            </div>

            <div class="control-group">
                <label>HVAC Vent Temperature Adjust</label>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 4px;">
                    <span id="ambientValLabel">22.0°C</span>
                </div>
                <input type="range" class="range-slider" id="ambientSlider" min="15.0" max="30.0" step="0.5" value="22.0" oninput="adjustAmbient(this.value)">
            </div>

            <div style="margin-top: auto; display: flex; gap: 8px;">
                <button style="flex: 1; border-color: var(--neon-red); color: var(--neon-red);" onclick="purgeDatabase()">Purge Logs</button>
            </div>
        </div>
    </div>

    <div class="grid-layout">
        <!-- scrolling debug terminal -->
        <div class="terminal-section">
            <div class="terminal-header">
                <span>JSON Telemetry Payload Console (RAW Ingestion Buffer)</span>
                <span>WROOM-32 Stream</span>
            </div>
            <div id="terminalLogs" class="terminal-logs">
                <div class="terminal-line">[SYSTEM] Terminal initialized. Waiting for serial link...</div>
            </div>
        </div>
    </div>

    <script>
        // Init chart
        const ctx = document.getElementById('telemetryChart').getContext('2d');
        const telemetryChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Seat Pan (HW-02A)',
                        data: [],
                        borderColor: '#ff6600',
                        backgroundColor: 'rgba(255, 102, 0, 0.05)',
                        borderWidth: 2,
                        tension: 0.3,
                        fill: true,
                        pointRadius: 0
                    },
                    {
                        label: 'Ambient Air (HW-02B)',
                        data: [],
                        borderColor: '#00bfff',
                        backgroundColor: 'rgba(0, 191, 255, 0.05)',
                        borderWidth: 1.5,
                        borderDash: [4, 4],
                        tension: 0.3,
                        fill: true,
                        pointRadius: 0
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: {
                            color: '#8b949e',
                            font: { family: 'JetBrains Mono', size: 10 }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: '#21262d' },
                        ticks: { color: '#8b949e', font: { family: 'JetBrains Mono', size: 9 } }
                    },
                    y: {
                        grid: { color: '#21262d' },
                        ticks: { color: '#8b949e', font: { family: 'JetBrains Mono', size: 9 } }
                    }
                }
            }
        });

        // Add line to terminal
        function logToTerminal(message, type = 'info') {
            const container = document.getElementById('terminalLogs');
            const date = new Date();
            const timeStr = date.toTimeString().split(' ')[0];
            const milliseconds = String(date.getMilliseconds()).padStart(3, '0');
            
            let colorClass = 'accent-log';
            if (type === 'err') colorClass = 'style="color: var(--neon-red);"';
            if (type === 'warn') colorClass = 'style="color: var(--neon-orange);"';

            const logLine = document.createElement('div');
            logLine.className = 'terminal-line';
            logLine.innerHTML = `<span class="timestamp-log">[${timeStr}.${milliseconds}]</span> <span ${colorClass}>${message}</span>`;
            
            container.insertBefore(logLine, container.firstChild);
            
            // Trim logs to prevent overflow
            if (container.children.length > 50) {
                container.removeChild(container.lastChild);
            }
        }

        // Presence control
        async function setPresence(isSitting) {
            try {
                const response = await fetch('/api/simulate/state', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ is_sitting: isSitting })
                });
                const data = await response.json();
                
                document.getElementById('btnSitting').className = isSitting ? 'active' : '';
                document.getElementById('btnVacant').className = !isSitting ? 'active' : '';
                
                logToTerminal(`POST /api/simulate/state - Sensor State updated. Occupancy: ${isSitting ? 'SITTING' : 'VACANT'}`, 'warn');
            } catch (err) {
                logToTerminal(`FAILED to update state: ${err.message}`, 'err');
            }
        }

        // Ambient control
        async function adjustAmbient(val) {
            try {
                document.getElementById('ambientValLabel').innerText = parseFloat(val).toFixed(1) + '°C';
                const response = await fetch('/api/simulate/ambient', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ambient_temp: parseFloat(val) })
                });
                logToTerminal(`POST /api/simulate/ambient - Reference Ambient set to ${val}°C`, 'info');
            } catch (err) {
                logToTerminal(`FAILED to update ambient: ${err.message}`, 'err');
            }
        }

        // Purge logs
        async function purgeDatabase() {
            if (!confirm("Are you sure you want to purge all historical metrics?")) return;
            try {
                const response = await fetch('/api/purge', { method: 'POST' });
                logToTerminal(`POST /api/purge - SQLite telemetry database purged. Reset stats.`, 'err');
                await pollTelemetry();
            } catch (err) {
                logToTerminal(`FAILED to purge: ${err.message}`, 'err');
            }
        }

        // Fetch telemetry and render charts
        async function pollTelemetry() {
            try {
                // 1. Fetch Instant Summary
                const summaryRes = await fetch('/api/summary');
                const summary = await summaryRes.json();

                const delta = summary.delta_temp;
                const occCard = document.getElementById('occupancyCard');
                const occVal = document.getElementById('occupancyVal');
                const occSub = document.getElementById('occupancySub');
                const badge = document.getElementById('badgeText');
                
                if (summary.is_occupied) {
                    occCard.className = 'card active-presence';
                    occVal.innerText = 'OCCUPIED';
                    occVal.style.color = 'var(--neon-orange)';
                    occSub.innerText = `Delta is compliant (>= 2.5°C)`;
                    badge.innerText = 'PRESENCE DETECTED';
                    badge.style.color = 'var(--neon-orange)';
                } else {
                    occCard.className = 'card';
                    occVal.innerText = 'VACANT';
                    occVal.style.color = 'var(--text-secondary)';
                    occSub.innerText = `Delta is sub-optimal (< 2.5°C)`;
                    badge.innerText = 'CHAIR INACTIVE';
                    badge.style.color = 'var(--text-secondary)';
                }

                document.getElementById('deltaVal').innerText = (delta >= 0 ? '+' : '') + delta.toFixed(2) + '°C';
                document.getElementById('tempDeets').innerText = `Seat: ${summary.chair_temp.toFixed(2)}°C // Ambient: ${summary.ambient_temp.toFixed(2)}°C`;
                
                document.getElementById('complianceVal').innerText = summary.compliance_percentage.toFixed(1) + '%';
                document.getElementById('cumulativeVal').innerText = `Elapsed presence: ${summary.cumulative_hours.toFixed(2)} hours`;

                // Log raw telemetry format as if received by serial / HTTP post
                const mockPayload = {
                    sensor_id: summary.sensor_id,
                    chair_temp: summary.chair_temp,
                    ambient_temp: summary.ambient_temp,
                    delta_t: summary.delta_temp,
                    status: summary.is_occupied ? "OCCUPIED" : "VACANT"
                };
                logToTerminal(`RX /telemetry JSON: ${JSON.stringify(mockPayload)}`, 'info');

                // 2. Fetch Time-Series History
                const historyRes = await fetch('/api/history');
                const history = await historyRes.json();

                const timestamps = history.map(h => {
                    const d = new Date(h.timestamp * 1000);
                    return d.toTimeString().split(' ')[0];
                });
                const chairTemps = history.map(h => h.chair_temp);
                const ambientTemps = history.map(h => h.ambient_temp);

                telemetryChart.data.labels = timestamps;
                telemetryChart.data.datasets[0].data = chairTemps;
                telemetryChart.data.datasets[1].data = ambientTemps;
                telemetryChart.update('none'); // silent update

            } catch (err) {
                logToTerminal(`Error polling database: ${err.message}`, 'err');
            }
        }

        // Initialize state slider on load
        document.getElementById('ambientSlider').value = 22.0;

        // Poll every 1.0 second
        setInterval(pollTelemetry, 1000);
        pollTelemetry();
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """
    Serves the primary graphical control center UI.
    """
    return DASHBOARD_HTML

if __name__ == "__main__":
    import uvicorn
    # Bound to local loopback to avoid security exposure of the dashboard interface
    uvicorn.run(app, host="127.0.0.1", port=8000)
