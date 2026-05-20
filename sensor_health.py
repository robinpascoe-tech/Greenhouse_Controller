#!/usr/bin/env python3

import pymysql
import statistics
from datetime import datetime, timezone, timedelta


# ============================================================
# DB
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
# FETCH (PYTHON-CONTROLLED WINDOW)
# ============================================================

def fetch(cur, sensor, hours):
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
    values = []
    crc = []

    for raw, crc_fail in rows:
        values.extend([float(x) for x in raw.split(",") if x])
        crc.append(crc_fail or 0)

    return values, crc


# ============================================================
# FEATURE ENGINEERING (CLEANED)
# ============================================================

def features(cur, sensor):

    w1_rows = fetch(cur, sensor, 1)
    w6_rows = fetch(cur, sensor, 6)
    w24_rows = fetch(cur, sensor, 24)

    w1, crc1 = parse(w1_rows)
    w6, _ = parse(w6_rows)
    w24, _ = parse(w24_rows)

    if len(w1) < 8:
        return None

    def stats(x):
        return {
            "median": statistics.median(x),
            "var": statistics.pvariance(x) if len(x) > 1 else 0,
            "n": len(x)
        }

    s1, s6, s24 = stats(w1), stats(w6), stats(w24)

    crc_rate = sum(crc1) / max(1, len(crc1))

    return {
        "variance": s1["var"],
        "drift_short": abs(s1["median"] - s6["median"]),
        "drift_long": abs(s1["median"] - s24["median"]),
        "sample_size": s1["n"],
        "noise_ratio": len(set(w1)) / max(1, len(w1)),
        "crc_rate": crc_rate
    }


# ============================================================
# CONFIDENCE MODEL (IMPROVED)
# ============================================================

def confidence(f):

    if not f:
        return 0.0

    sample_factor = min(1.0, f["sample_size"] / 20)
    noise_factor = 1.0 - f["noise_ratio"]

    return round((sample_factor * 0.7 + noise_factor * 0.3), 3)


# ============================================================
# SCORING (EMA-INTEGRATED)
# ============================================================

def score(f, ema_health):

    if not f:
        return 0, "no data"

    score = 100
    notes = []

    # EMA influence (IMPORTANT v3.1 FIX)
    if ema_health:
        score = (score * 0.7) + (ema_health * 0.3)

    # variance
    if f["variance"] > 1.0:
        score -= 20
        notes.append("high noise")

    # drift
    if f["drift_short"] > 0.8:
        score -= 15
        notes.append("short drift")

    if f["drift_long"] > 1.2:
        score -= 20
        notes.append("long drift")

    # CRC (now properly integrated)
    if f["crc_rate"] > 0.3:
        score -= 25
        notes.append("crc instability")
    elif f["crc_rate"] > 0.1:
        score -= 10

    return max(0, score), ", ".join(notes) or "ok"


# ============================================================
# STATUS MACHINE (RECOVERY FIXED)
# ============================================================

def decide(new_score, prev_status):

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
# STATE UPDATE (FIXED EMA + RECOVERY)
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

    # RECOVERY IS NOW PERSISTENT
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

        health, notes = score(f, ema)
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

    con.close()


if __name__ == "__main__":
    main()
