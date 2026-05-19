#!/usr/bin/env python3

from flask import Flask, jsonify, render_template_string
import subprocess
import pymysql as mdb

app = Flask(__name__)


# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

GPIO_MAP = {
    "WINDOW_REVERSER": 22,
    "WINDOW_MOTOR": 17,
    "ROOF_REVERSER": 9,
    "ROOF_MOTOR": 10,
    "VENT_FAN": 5,
    "AUX_VENT_FAN": 11,
    "HEATER": 19,
    "CIRC_FAN": 6,
}

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "change_this_password",
    "database": "greenhouse",
}


# ─────────────────────────────────────────────
# GPIO (pinctrl parser)
# ─────────────────────────────────────────────

def read_all_gpio():
    try:
        output = subprocess.check_output(["pinctrl", "get"], text=True)
    except Exception:
        return {}

    states = {}

    for line in output.splitlines():
        line = line.lower()

        if ":" not in line:
            continue

        try:
            pin = int(line.split(":")[0])

            if " hi " in line or "| hi" in line:
                states[pin] = 1
            else:
                states[pin] = 0

        except:
            continue

    return states


# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────

def db():
    return mdb.connect(**DB_CONFIG)


def get_temps():
    con = db()
    cur = con.cursor()

    cur.execute("""
        SELECT temperature, temperatureF, timestamp
        FROM currenttemp
        ORDER BY id DESC
        LIMIT 60
    """)

    rows = cur.fetchall()
    con.close()

    return list(reversed(rows))


def get_status():
    con = db()
    cur = con.cursor()

    cur.execute("""
        SELECT heater, fan, circfan, window, timestamp
        FROM status_log
        ORDER BY id DESC
        LIMIT 60
    """)

    rows = cur.fetchall()
    con.close()

    return list(reversed(rows))


# ─────────────────────────────────────────────
# HTML
# ─────────────────────────────────────────────

HTML = """
<!doctype html>
<html>
<head>
    <title>Greenhouse Dashboard</title>

    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns"></script>

    <style>
        body { font-family: Arial; background:#111; color:#eee; }

        .grid {
            display:grid;
            grid-template-columns: 1fr 1fr;
            gap:20px;
        }

        .panel {
            background:#222;
            padding:15px;
            border-radius:10px;
        }

        table {
            width:100%;
            border-collapse: collapse;
        }

        td, th {
            border:1px solid #444;
            padding:5px;
        }

        .on { background:#2ecc71; color:#000; }
        .off { background:#e74c3c; color:#fff; }

        canvas {
            background:#fff;
            border-radius:8px;
        }
    </style>
</head>

<body>

<h2>🌱 Greenhouse SCADA Dashboard</h2>

<div class="grid">

<!-- GPIO -->
<div class="panel">
<h3>GPIO Status</h3>
<table>
<tr><th>Device</th><th>Pin</th><th>Status</th></tr>
<tbody id="gpioTable"></tbody>
</table>
</div>

<!-- STATUS -->
<div class="panel">
<h3>System Status</h3>
<ul id="statusBox"></ul>
</div>

<!-- TEMP -->
<div class="panel">
<h3>Temperature (°C)</h3>
<canvas id="tempChart"></canvas>
</div>

<!-- ACTUATORS -->
<div class="panel">
<h3>Actuator States</h3>
<canvas id="stateChart"></canvas>
</div>

</div>

<script>

const GPIO_MAP = {{ gpio_map | tojson }};

let tempChart, stateChart;


// ─────────────────────────────────────
// CHART INIT
// ─────────────────────────────────────

function initCharts(){

    tempChart = new Chart(
        document.getElementById("tempChart"),
        {
            type: "line",
            data: {
                datasets: [{
                    label: "Temperature °C",
                    data: [],
                    borderColor: "red"
                }]
            },
            options: {
                scales: {
                    x: {
                        type: "time",
                        time: {
                            unit: "minute"
                        }
                    }
                }
            }
        }
    );

    stateChart = new Chart(
        document.getElementById("stateChart"),
        {
            type: "line",
            data: {
                datasets: [
                    { label:"Heater", data:[], borderColor:"orange" },
                    { label:"Fan", data:[], borderColor:"blue" },
                    { label:"Window", data:[], borderColor:"green" }
                ]
            },
            options: {
                scales: {
                    x: {
                        type: "time"
                    },
                    y: {
                        min: 0,
                        max: 1
                    }
                }
            }
        }
    );
}


// ─────────────────────────────────────
// GPIO UPDATE (1s)
// ─────────────────────────────────────

async function updateGPIO(){

    const gpio = await fetch('/api/gpio').then(r => r.json());

    let html = "";

    for (const [name, pin] of Object.entries(GPIO_MAP)) {

        const state = gpio[pin] ?? 0;

        html += `
        <tr>
            <td>${name}</td>
            <td>${pin}</td>
            <td class="${state ? 'on' : 'off'}">
                ${state ? 'ON' : 'OFF'}
            </td>
        </tr>`;
    }

    document.getElementById("gpioTable").innerHTML = html;
}


// ─────────────────────────────────────
// SLOW UPDATE (5s)
// ─────────────────────────────────────

async function updateSlow(){

    const temps = await fetch('/api/temps').then(r => r.json());
    const state = await fetch('/api/status').then(r => r.json());

    // STATUS
    if (state.length > 0) {
        const last = state[state.length - 1];

        document.getElementById("statusBox").innerHTML = `
            <li>Heater: ${last[0]}</li>
            <li>Fan: ${last[1]}</li>
            <li>Circulation: ${last[2]}</li>
            <li>Window: ${last[3]}</li>
        `;
    }

    // TEMP GRAPH (FIXED)
    const baseTime = new Date(temps[0][2]).getTime();

    tempChart.data.datasets[0].data = temps.map((x, i) => ({
        x: new Date(baseTime + i * 60000), // force 1-min spacing
        y: parseFloat(x[0])
    }));

    tempChart.update();

    // ACTUATOR GRAPH (FIXED)
    stateChart.data.datasets[0].data = state.map(x => ({
        x: new Date(x[4]),
        y: Number(x[0])
    }));

    stateChart.data.datasets[1].data = state.map(x => ({
        x: new Date(x[4]),
        y: Number(x[1])
    }));

    stateChart.data.datasets[2].data = state.map(x => ({
        x: new Date(x[4]),
        y: Number(x[3])
    }));

    stateChart.update();
}


// ─────────────────────────────────────
// STARTUP
// ─────────────────────────────────────

initCharts();

updateGPIO();
setInterval(updateGPIO, 1000);

updateSlow();
setInterval(updateSlow, 5000);

</script>

</body>
</html>
"""


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(
        HTML,
        gpio_map=GPIO_MAP
    )


@app.route("/api/gpio")
def api_gpio():
    return jsonify(read_all_gpio())


@app.route("/api/temps")
def api_temps():
    return jsonify(get_temps())


@app.route("/api/status")
def api_status():
    return jsonify(get_status())


# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("Greenhouse dashboard running on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
