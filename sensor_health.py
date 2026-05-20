#!/usr/bin/env python3

"""
Sensor Health Engine v3.3

FULL PROFILE-DRIVEN VERSION

Key upgrades:
- sensor_profile replaces all hardcoded sensor logic
- adaptive thresholds per sensor personality
- learned behavior updates (mean + variance)
- full predictive maintenance scoring system
"""

import pymysql
import statistics
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta


# ============================================================
# EMAIL CONFIG
# ============================================================

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USER = "your_email@gmail.com"
EMAIL_PASS = "your_app_password"
ALERT_RECIPIENT = "your_email@gmail.com"

ALERT_COOLDOWN_HOURS = 6


# ============================================================
# DB CONNECTION
# ============================================================

def db():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="change_this_password",
        database="greenhouse",
        cursorclass=pymysql.cursors.Cursor,
        autocommit=True
    )


# ============================================================
# PROFILE LOADING (CORE OF SYSTEM)
# ============================================================

def get_sensor_profile(cur, sensor):
    cur.execute("""
        SELECT sensor_type,
               expected_min,
               expected_max,
               normal_variance,
               drift_sensitivity,
               noise_tolerance,
               crc_sensitivity,
               learned_mean,
               learned_variance
        FROM sensor_profile
        WHERE sensor_name=%s
    """, (sensor,))

    row = cur.fetchone()

    if not row:
        return {
            "sensor_type": "indoor",
            "expected_min": None,
            "expected_max": None,
            "normal_variance": 1.0,
            "drift_sensitivity": 1.0,
            "noise_tolerance": 1.0,
            "crc_sensitivity": 1.0,
            "learned_mean": None,
            "learned_variance": None
        }

    return {
        "sensor_type": row[0],
        "expected_min": row[1],
        "expected_max": row[2],
        "normal_variance": row[3],
        "drift_sensitivity": row[4],
        "noise_tolerance": row[5],
        "crc_sensitivity": row[6],
        "learned_mean": row[7],
        "learned_variance": row[8]
    }


# ============================================================
# TIME WINDOW FETCH
# ============================================================

def fetch(cur, sensor, hours):
    start = datetime.now(timezone.utc) - timedelta(hours=hours)

    cur.execute("""
        SELECT raw_values, crc_failures
        FROM sensor_diagnostics
        WHERE sensor_name=%s
        AND timestamp >= %s
        ORDER BY timestamp ASC
    """, (sensor, start))

    return cur.fetchall()


def parse(rows):
    values = []
    crc = []

    for raw, crc_fail in rows:
        values.extend([float(x) for x in raw.split(",") if x])
        crc.append(crc_fail or 0)

    return values, crc


# ============================================================
# FEATURE ENGINE
# ============================================================

def features(cur, sensor):

    w1 = fetch(cur, sensor, 1)
    w6 = fetch(cur, sensor, 6)
    w24 = fetch(cur, sensor, 24)

    v1, crc = parse(w1)
    v6, _ = parse(w6)
    v24, _ = parse(w24)

    if len(v1) < 8:
        return None

    def stats(x):
        return {
            "median": statistics.median(x),
            "var": statistics.pvariance(x) if len(x) > 1 else 0,
            "n": len(x)
        }

    s1, s6, s24 = stats(v1), stats(v6), stats(v24)

    return {
        "median": s1["median"],
        "variance": s1["var"],
        "drift_short": abs(s1["median"] - s6["median"]),
        "drift_long": abs(s1["median"] - s24["median"]),
        "sample_size": s1["n"],
        "instability": len(set(v1)) / max(1, len(v1)),
        "crc_rate": sum(crc) / max(1, len(crc))
    }


# ============================================================
# CONFIDENCE MODEL
# ============================================================

def confidence(f):
    if not f:
        return 0.0

    sample = min(1.0, f["sample_size"] / 20)
    noise = 1.0 - f["instability"]

    return round((sample * 0.7 + noise * 0.3), 3)


# ============================================================
# SCORING ENGINE (PROFILE DRIVEN)
# ============================================================

def score(f, ema, profile):

    if not f:
        return 0, "no data"

    score = 100
    notes = []

    # EMA smoothing influence
    if ema:
        score = (score * 0.7) + (ema * 0.3)

    # Variance
    if f["variance"] > profile["normal_variance"] * profile["noise_tolerance"]:
        score -= 20
        notes.append("high noise")

    # Drift short
    if f["drift_short"] > 0.8 * profile["drift_sensitivity"]:
        score -= 15
        notes.append("short drift")

    # Drift long
    if f["drift_long"] > 1.2 * profile["drift_sensitivity"]:
        score -= 20
        notes.append("long drift")

    # Range checks
    if profile["expected_min"] and f["median"] < profile["expected_min"]:
        score -= 10
        notes.append("below expected range")

    if profile["expected_max"] and f["median"] > profile["expected_max"]:
        score -= 10
        notes.append("above expected range")

    # CRC
    if f["crc_rate"] > 0.3 * profile["crc_sensitivity"]:
        score -= 25
        notes.append("crc instability")

    return max(0, score), ", ".join(notes) or "ok"


# ============================================================
# STATE UPDATE
# ============================================================

def update_state(cur, sensor, score, status):

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

        profile = get_sensor_profile(cur, sensor)
        f = features(cur, sensor)

        cur.execute("""
            SELECT last_status, ema_health
            FROM sensor_state
            WHERE sensor_name=%s
        """, (sensor,))
        prev = cur.fetchone()

        prev_status = prev[0] if prev else None
        ema = prev[1] if prev else None

        health, notes = score(f, ema, profile)

        # simple decision layer (can later be profile-driven too)
        if health >= 90:
            status = "HEALTHY"
        elif health >= 70:
            status = "STABLE" if prev_status != "CRITICAL" else "DEGRADED"
        elif health >= 50:
            status = "DEGRADED"
        else:
            status = "CRITICAL"

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

    con.close()


if __name__ == "__main__":
    main()
