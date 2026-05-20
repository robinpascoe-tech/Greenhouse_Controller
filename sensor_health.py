#!/usr/bin/env python3

"""
Sensor Health Engine v3.2

Predictive telemetry system for DS18B20 sensors.

Improvements over v3.1:
- Renamed noise_ratio → instability_ratio (clarity fix)
- Added sensor-type baselines (context-aware scoring)
- Restored email alert system (with cooldown protection)
- Fully commented for long-term maintainability
"""

import pymysql
import statistics
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta


# ============================================================
# EMAIL CONFIGURATION (EXTERNAL ALERT SYSTEM)
# ============================================================

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USER = "your_email@gmail.com"
EMAIL_PASS = "your_app_password"
ALERT_RECIPIENT = "your_email@gmail.com"

ALERT_COOLDOWN_HOURS = 6


# ============================================================
# DATABASE CONNECTION
# ============================================================

def db():
    """Create MySQL connection (cron-safe, lightweight)."""
    return pymysql.connect(
        host="localhost",
        user="root",
        password="change_this_password",
        database="greenhouse",
        cursorclass=pymysql.cursors.Cursor,
        autocommit=True
    )


# ============================================================
# EMAIL ALERT FUNCTION
# ============================================================

def send_email(subject, body):
    """Send alert email via SMTP."""
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = ALERT_RECIPIENT

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, ALERT_RECIPIENT, msg.as_string())
        server.quit()
    except Exception as e:
        print(f"[ALERT ERROR] Email failed: {e}")


# ============================================================
# SENSOR TYPE BASLINES (NEW FEATURE)
# ============================================================

def sensor_type(sensor_name):
    """
    Defines expected behavior profile per sensor type.

    This prevents false positives from inherently noisy sensors.
    """

    outdoor = ["OutsideTemp"]
    high_variance = ["WoodStoveTemp"]

    if sensor_name in outdoor:
        return "outdoor"
    if sensor_name in high_variance:
        return "high_variance"
    return "indoor"


def baseline_adjustments(sensor_type):
    """
    Adjusts thresholds based on sensor environment.
    """

    if sensor_type == "outdoor":
        return {"variance_mult": 1.5, "drift_mult": 1.3}

    if sensor_type == "high_variance":
        return {"variance_mult": 2.0, "drift_mult": 1.8}

    return {"variance_mult": 1.0, "drift_mult": 1.0}


# ============================================================
# DATA FETCHING (TIME-BASED WINDOWS)
# ============================================================

def fetch(cur, sensor, hours):
    """
    Pull sensor diagnostics for a rolling time window.
    """
    start_time = datetime.now(timezone.utc) - timedelta(hours=hours)

    cur.execute("""
        SELECT raw_values, crc_failures
        FROM sensor_diagnostics
        WHERE sensor_name=%s
        AND timestamp >= %s
        ORDER BY timestamp ASC
    """, (sensor, start_time))

    return cur.fetchall()


def parse(rows):
    """
    Convert DB rows into:
    - float temperature values
    - CRC failure counts
    """

    values = []
    crc = []

    for raw, crc_fail in rows:
        values.extend([float(x) for x in raw.split(",") if x])
        crc.append(crc_fail or 0)

    return values, crc


# ============================================================
# FEATURE ENGINEERING (TIME-SERIES INTELLIGENCE)
# ============================================================

def features(cur, sensor):
    """
    Extracts multi-window statistical features:
    - short term (1h)
    - medium term (6h)
    - long term (24h)
    """

    w1 = fetch(cur, sensor, 1)
    w6 = fetch(cur, sensor, 6)
    w24 = fetch(cur, sensor, 24)

    w1_vals, w1_crc = parse(w1)
    w6_vals, _ = parse(w6)
    w24_vals, _ = parse(w24)

    # Require minimum data for stability
    if len(w1_vals) < 8:
        return None

    def stats(x):
        return {
            "median": statistics.median(x),
            "var": statistics.pvariance(x) if len(x) > 1 else 0,
            "n": len(x)
        }

    s1, s6, s24 = stats(w1_vals), stats(w6_vals), stats(w24_vals)

    return {
        "variance": s1["var"],
        "drift_short": abs(s1["median"] - s6["median"]),
        "drift_long": abs(s1["median"] - s24["median"]),
        "sample_size": s1["n"],

        # RENAMED for clarity (was noise_ratio)
        "instability_ratio": len(set(w1_vals)) / max(1, len(w1_vals)),

        "crc_rate": sum(w1_crc) / max(1, len(w1_crc))
    }


# ============================================================
# CONFIDENCE MODEL (DATA QUALITY ESTIMATION)
# ============================================================

def confidence(f):
    """
    Estimates reliability of computed metrics.
    """

    if not f:
        return 0.0

    sample_factor = min(1.0, f["sample_size"] / 20)
    stability_factor = 1.0 - f["instability_ratio"]

    return round((sample_factor * 0.7 + stability_factor * 0.3), 3)


# ============================================================
# HEALTH SCORING (WITH SENSOR BASELINES)
# ============================================================

def score(f, ema_health, sensor_type_info):

    if not f:
        return 0, "no data"

    score = 100
    notes = []

    # Apply EMA smoothing (system memory influence)
    if ema_health:
        score = (score * 0.7) + (ema_health * 0.3)

    adj = baseline_adjustments(sensor_type_info)

    # Variance (adjusted by sensor type)
    if f["variance"] > 1.0 * adj["variance_mult"]:
        score -= 20
        notes.append("high noise")

    # Drift detection (adjusted thresholds)
    if f["drift_short"] > 0.8 * adj["drift_mult"]:
        score -= 15
        notes.append("short drift")

    if f["drift_long"] > 1.2 * adj["drift_mult"]:
        score -= 20
        notes.append("long drift")

    # CRC instability (strong failure signal)
    if f["crc_rate"] > 0.3:
        score -= 25
        notes.append("crc instability")
    elif f["crc_rate"] > 0.1:
        score -= 10

    return max(0, score), ", ".join(notes) or "ok"


# ============================================================
# STATE MACHINE (WITH RECOVERY LOGIC)
# ============================================================

def decide(new_score, prev_status):
    """
    Converts score into system state with hysteresis.
    """

    if new_score >= 90:
        return "HEALTHY"

    if new_score >= 70:
        if prev_status == "CRITICAL":
            return "DEGRADED"
        return "STABLE"

    if new_score >= 50:
        return "DEGRADED"

    return "CRITICAL"


# ============================================================
# ALERT SYSTEM (EMAIL + COOLDOWN)
# ============================================================

def can_alert(cur, sensor):
    """
    Prevents alert spam using cooldown window.
    """

    cur.execute("""
        SELECT last_change_time
        FROM sensor_state
        WHERE sensor_name=%s
    """, (sensor,))

    row = cur.fetchone()

    if not row:
        return True

    last_time = row[0]

    if not last_time:
        return True

    delta = (datetime.now(timezone.utc) - last_time).total_seconds()

    return delta > ALERT_COOLDOWN_HOURS * 3600


def alert(cur, sensor, status, score):
    """
    Sends external notification (email).
    """

    if not can_alert(cur, sensor):
        return

    subject = f"[GREENHOUSE ALERT] {sensor} → {status}"

    body = f"""
Sensor: {sensor}
Status: {status}
Health Score: {score}

Time: {datetime.now(timezone.utc)}
"""

    send_email(subject, body)


# ============================================================
# STATE UPDATE (EMA + MEMORY)
# ============================================================

def update_state(cur, sensor, score, status):
    """
    Stores persistent sensor memory (EMA + last state).
    """

    cur.execute("""
        SELECT last_status, ema_health
        FROM sensor_state
        WHERE sensor_name=%s
    """, (sensor,))

    row = cur.fetchone()

    if not row:
        cur.execute("""
            INSERT INTO sensor_state
            (sensor_name, last_status, last_health, ema_health, last_change_time)
            VALUES (%s,%s,%s,%s,NOW())
        """, (sensor, status, score, score))
        return

    last_status, ema = row

    ema = (ema or score) * 0.8 + score * 0.2

    # Recovery detection
    if last_status in ["DEGRADED", "CRITICAL"] and score >= 85:
        status = "RECOVERED"

    cur.execute("""
        UPDATE sensor_state
        SET last_status=%s,
            last_health=%s,
            ema_health=%s,
            last_change_time=NOW()
        WHERE sensor_name=%s
    """, (status, score, ema, sensor))


# ============================================================
# MAIN LOOP
# ============================================================

def main():

    con = db()
    cur = con.cursor()

    cur.execute("SELECT DISTINCT sensor_name FROM sensor_diagnostics")
    sensors = [r[0] for r in cur.fetchall()]

    now = datetime.now(timezone.utc)

    for sensor in sensors:

        f = features(cur, sensor)

        cur.execute("""
            SELECT last_status, ema_health
            FROM sensor_state
            WHERE sensor_name=%s
        """, (sensor,))
        prev = cur.fetchone()

        prev_status = prev[0] if prev else None
        ema = prev[1] if prev else None

        s_type = sensor_type(sensor)

        health, notes = score(f, ema, s_type)
        status = decide(health, prev_status)

        conf = confidence(f)

        cur.execute("""
            INSERT INTO sensor_health
            (sensor_name, timestamp, health_score, status,
             crc_rate, variance, drift_short, drift_long,
             confidence, notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            sensor,
            now,
            health,
            status,
            f["crc_rate"] if f else 0,
            f["variance"] if f else 0,
            f["drift_short"] if f else 0,
            f["drift_long"] if f else 0,
            conf,
            notes
        ))

        update_state(cur, sensor, health, status)

        # External alert system (RESTORED)
        if status in ["DEGRADED", "CRITICAL", "RECOVERED"]:
            alert(cur, sensor, status, health)

    con.close()


if __name__ == "__main__":
    main()
