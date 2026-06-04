#!/usr/bin/env python3
"""
Sensor Health Engine v3.3.1 (Stabilization + Peer Context)

This version focuses on:
- Fixing regressions introduced in v3.3
- Restoring operational alerting
- Preventing status oscillation (hysteresis)
- Unifying decision logic with sensor profiles
- Adding peer/environment context for normal greenhouse temperature gradients
- Improving maintainability and debugging clarity

This is intended to run as a cron-based process on a Raspberry Pi.
"""

import pymysql
import statistics
import smtplib
import configparser
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta


# ============================================================
# ALERT CONFIGURATION
# ============================================================

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USER = "your_email@gmail.com"
EMAIL_PASS = "your_app_password"
ALERT_RECIPIENT = "your_email@gmail.com"

ALERTS_ENABLED = False
ALERT_COOLDOWN_HOURS = 6

DS18B20_SENTINEL_VALUES = {-127.0, 85.0}

INDOOR_SENSOR_GROUP = "inside_air"
OUTDOOR_SENSOR_GROUP = "outside_air"
DERIVED_SENSOR_GROUP = "derived"
SPECIAL_SENSOR_GROUP = "special"

KNOWN_SENSOR_GROUPS = {
    "AverageInsideTemp": DERIVED_SENSOR_GROUP,
    "OutsideTemp": OUTDOOR_SENSOR_GROUP,
    "PiTemp": SPECIAL_SENSOR_GROUP,
    "WoodstoveTemp": SPECIAL_SENSOR_GROUP,
}

ENVIRONMENTAL_SHORT_DRIFT_C = 0.8
ENVIRONMENTAL_LONG_DRIFT_C = 1.2
PEER_DIRECTION_EPSILON_C = 0.25
PEER_OUTLIER_MIN_C = 3.0
PEER_OUTLIER_MAD_MULTIPLIER = 4.0


# ============================================================
# DATABASE CONNECTION
# ============================================================

config = configparser.ConfigParser()
config.read("/home/pi/Greenhouse_Controller/greenhouse.conf")

try:
    DB_HOST = config["database"]["host"]
    DB_USER = config["database"]["user"]
    DB_PASSWORD = config["database"]["password"]
    DB_NAME = config["database"]["database"]
except Exception:
    DB_HOST = "localhost"
    DB_USER = "greenhouse_app"
    DB_PASSWORD = "change_this_password"
    DB_NAME = "greenhouse"

ALERTS_ENABLED = config.getboolean("alerts", "enabled", fallback=ALERTS_ENABLED)
SMTP_SERVER = config.get("alerts", "smtp_server", fallback=SMTP_SERVER)
SMTP_PORT = config.getint("alerts", "smtp_port", fallback=SMTP_PORT)
EMAIL_USER = config.get("alerts", "email_user", fallback=EMAIL_USER)
EMAIL_PASS = config.get("alerts", "email_password", fallback=EMAIL_PASS)
ALERT_RECIPIENT = config.get("alerts", "recipient", fallback=ALERT_RECIPIENT)
ALERT_COOLDOWN_HOURS = config.getfloat(
    "alerts",
    "cooldown_hours",
    fallback=ALERT_COOLDOWN_HOURS,
)


def as_utc(value):
    """Treat naive MySQL DATETIME values as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def db():
    """Create lightweight cron-safe MySQL connection."""
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.Cursor,
        connect_timeout=5,
        autocommit=True
    )


# ============================================================
# SENSOR PROFILE LOADING
# ============================================================

def get_sensor_profile(cur, sensor):
    """
    Load full sensor personality profile.

    This defines:
    - expected operating range
    - sensitivity to drift/noise/CRC errors
    - learned behavior baselines
    """

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

    # Safe fallback profile (prevents NULL logic failures)
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

    normal_variance = row[3] if row[3] is not None else 1.0
    drift_sensitivity = row[4] if row[4] is not None else 1.0
    noise_tolerance = row[5] if row[5] is not None else 1.0
    crc_sensitivity = row[6] if row[6] is not None else 1.0

    return {
        "sensor_type": row[0],
        "expected_min": row[1],
        "expected_max": row[2],
        "normal_variance": float(normal_variance),
        "drift_sensitivity": float(drift_sensitivity),
        "noise_tolerance": float(noise_tolerance),
        "crc_sensitivity": float(crc_sensitivity),
        "learned_mean": row[7],
        "learned_variance": row[8]
    }


def sensor_group(sensor, profile):
    """
    Return the comparison group for a sensor.

    The grouping is deliberately role based rather than name-count based. A
    larger greenhouse can add more `sensor_profile.sensor_type='indoor'`
    sensors and they will join the same inside-air peer group automatically.
    Known derived/special sensors are excluded from peer voting because they do
    not represent independent greenhouse air measurements.
    """

    if sensor in KNOWN_SENSOR_GROUPS:
        return KNOWN_SENSOR_GROUPS[sensor]

    sensor_type = str(profile.get("sensor_type") or "").lower()

    if sensor_type in {"indoor", "inside", "inside_air", "greenhouse"}:
        return INDOOR_SENSOR_GROUP

    if sensor_type in {"outdoor", "outside", "outside_air"}:
        return OUTDOOR_SENSOR_GROUP

    if sensor_type in {"derived", "computed", "average"}:
        return DERIVED_SENSOR_GROUP

    return SPECIAL_SENSOR_GROUP


# ============================================================
# TIME WINDOW DATA EXTRACTION
# ============================================================

def fetch(cur, sensor, hours):
    """
    Retrieve sensor diagnostics within a rolling time window.
    """
    start_time = datetime.now(timezone.utc) - timedelta(hours=hours)

    cur.execute("""
        SELECT raw_values, crc_failures, notes
        FROM sensor_diagnostics
        WHERE sensor_name=%s
        AND timestamp >= %s
        ORDER BY timestamp ASC
    """, (sensor, start_time))

    return cur.fetchall()


def parse(rows):
    """
    Convert raw DB rows into usable numeric series.

    DS18B20 sentinel values are counted as invalid instead of being treated as
    real temperatures. Common examples are 85 C after power-up and -127 C when
    the sensor is disconnected or unreadable.
    """

    values = []
    crc = []
    failure_rows = 0
    invalid_readings = 0

    for raw, crc_fail, notes in rows:
        row_values = 0
        for item in str(raw or "").split(","):
            item = item.strip()
            if not item:
                continue
            try:
                value = float(item)
                if value in DS18B20_SENTINEL_VALUES:
                    invalid_readings += 1
                    continue

                values.append(value)
                row_values += 1
            except ValueError:
                continue

        crc.append(crc_fail or 0)

        if row_values == 0 or str(notes or "").upper() in {"FAILED", "FAIL"}:
            failure_rows += 1

    return values, crc, failure_rows, invalid_readings


# ============================================================
# FEATURE ENGINEERING (TIME SERIES INTELLIGENCE)
# ============================================================

def features(cur, sensor):
    """
    Builds statistical representation of sensor behavior:
    - short-term (1h)
    - mid-term (6h)
    - long-term (24h)
    """

    w1 = fetch(cur, sensor, 1)
    w6 = fetch(cur, sensor, 6)
    w24 = fetch(cur, sensor, 24)

    v1, crc, failures, invalid_readings = parse(w1)
    v6, _, _, _ = parse(w6)
    v24, _, _, _ = parse(w24)

    # Not enough samples for trend math. If all rows are failures/sentinels,
    # return an explicit failure feature set so the caller can alert.
    if len(v1) < 8:
        if w1 and not v1 and (failures or invalid_readings):
            return {
                "median": None,
                "variance": 0,
                "drift_short": 0,
                "drift_long": 0,
                "sample_size": 0,
                "instability_ratio": 1.0,
                "crc_rate": sum(crc) / max(1, len(crc)),
                "failure_rows": failures,
                "invalid_readings": invalid_readings,
                "row_count": len(w1),
                "sensor_failure": True,
                "flatline": False
            }

        return None

    def stats(x):
        return {
            "median": statistics.median(x),
            "variance": statistics.pvariance(x) if len(x) > 1 else 0,
            "count": len(x)
        }

    s1 = stats(v1)
    s6 = stats(v6) if v6 else s1
    s24 = stats(v24) if v24 else s1

    drift_short_signed = s1["median"] - s6["median"]
    drift_long_signed = s1["median"] - s24["median"]

    return {
        "median": s1["median"],
        "variance": s1["variance"],
        "drift_short": abs(drift_short_signed),
        "drift_long": abs(drift_long_signed),
        "drift_short_signed": drift_short_signed,
        "drift_long_signed": drift_long_signed,
        "sample_size": s1["count"],
        "instability_ratio": len(set(v1)) / max(1, len(v1)),
        "crc_rate": sum(crc) / max(1, len(crc)),
        "failure_rows": failures,
        "invalid_readings": invalid_readings,
        "invalid_ratio": invalid_readings / max(1, len(v1) + invalid_readings),
        "row_count": len(w1),
        "sensor_failure": False,
        "flatline": len(w1) >= 3 and len(set(v1)) <= 1
    }


def _same_direction(a, b):
    """Return True when two temperature trends move meaningfully together."""

    if abs(a) < PEER_DIRECTION_EPSILON_C or abs(b) < PEER_DIRECTION_EPSILON_C:
        return False

    return (a > 0 and b > 0) or (a < 0 and b < 0)


def add_peer_context(sensor, profile, f, profiles, feature_map):
    """
    Add peer/environment context to a feature set.

    Normal greenhouse ramps can be uneven: the sunny front may heat faster than
    the back, and door/window events can cool one end first. Because of that,
    a two-sensor inside group is treated as context, not proof. Outlier
    penalties require at least three comparable independent sensors.
    """

    if not f or f.get("sensor_failure"):
        return f

    group = sensor_group(sensor, profile)
    f["sensor_group"] = group

    comparable_groups = {INDOOR_SENSOR_GROUP}
    if group not in comparable_groups:
        f["peer_group_size"] = 0
        f["environmental_change"] = False
        f["peer_outlier"] = False
        return f

    peers = []
    for peer_name, peer_features in feature_map.items():
        if not peer_features or peer_features.get("sensor_failure"):
            continue

        peer_profile = profiles.get(peer_name, {})
        if sensor_group(peer_name, peer_profile) != group:
            continue

        if peer_features.get("median") is None:
            continue

        peers.append((peer_name, peer_features))

    f["peer_group_size"] = len(peers)

    if len(peers) < 2:
        f["environmental_change"] = False
        f["peer_outlier"] = False
        return f

    medians = [peer_f["median"] for _, peer_f in peers]
    group_median = statistics.median(medians)
    deviations = [abs(value - group_median) for value in medians]
    group_mad = statistics.median(deviations) if deviations else 0
    peer_delta = abs(f["median"] - group_median)

    short_trends = [peer_f.get("drift_short_signed", 0) for _, peer_f in peers]
    long_trends = [peer_f.get("drift_long_signed", 0) for _, peer_f in peers]

    same_short = sum(
        1 for trend in short_trends if _same_direction(f["drift_short_signed"], trend)
    )
    same_long = sum(
        1 for trend in long_trends if _same_direction(f["drift_long_signed"], trend)
    )

    group_short_drift = statistics.median(abs(trend) for trend in short_trends)
    group_long_drift = statistics.median(abs(trend) for trend in long_trends)

    environmental_change = (
        group_short_drift >= ENVIRONMENTAL_SHORT_DRIFT_C
        or group_long_drift >= ENVIRONMENTAL_LONG_DRIFT_C
        or same_short >= 2
        or same_long >= 2
    )

    peer_outlier = False
    if len(peers) >= 3:
        outlier_threshold = max(
            PEER_OUTLIER_MIN_C,
            group_mad * PEER_OUTLIER_MAD_MULTIPLIER,
            float(profile.get("normal_variance") or 1.0) * 2.0,
        )
        peer_outlier = peer_delta > outlier_threshold

    f.update({
        "environmental_change": environmental_change,
        "peer_outlier": peer_outlier,
        "peer_delta": peer_delta,
        "peer_group_median": group_median,
        "peer_group_mad": group_mad,
        "peer_group_short_drift": group_short_drift,
        "peer_group_long_drift": group_long_drift,
    })

    return f


# ============================================================
# CONFIDENCE MODEL
# ============================================================

def confidence(f):
    """
    Estimates reliability of computed sensor metrics.

    Higher confidence = more stable + more data
    """

    if not f:
        return 0.0

    if f.get("sensor_failure"):
        return 0.0

    sample_factor = min(1.0, f["sample_size"] / 20)
    noise_factor = 1.0 - f["instability_ratio"]

    return round((sample_factor * 0.7 + noise_factor * 0.3), 3)


# ============================================================
# ALERT SYSTEM (RESTORED + SAFE)
# ============================================================

def send_email(subject, body):
    """Send SMTP email alert."""
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
        print(f"[ALERT ERROR] {e}")


def can_alert(cur, sensor, status):
    """
    Prevents alert spam using cooldown window.
    """
    cur.execute("""
        SELECT timestamp
        FROM sensor_alerts
        WHERE sensor_name=%s
        AND alert_type=%s
        ORDER BY timestamp DESC
        LIMIT 1
    """, (sensor, status))

    row = cur.fetchone()

    if not row or not row[0]:
        return True

    last_time = as_utc(row[0])
    delta = (datetime.now(timezone.utc) - last_time).total_seconds()

    return delta > ALERT_COOLDOWN_HOURS * 3600


def alert(cur, sensor, status, score):
    """Send alert if cooldown allows."""
    if not ALERTS_ENABLED:
        print(f"[ALERT DISABLED] {sensor} {status} score={score}")
        return

    if not can_alert(cur, sensor, status):
        return

    subject = f"[GREENHOUSE ALERT] {sensor} -> {status}"
    body = f"""
Sensor: {sensor}
Status: {status}
Score: {score}
Time: {datetime.now(timezone.utc)}
"""

    send_email(subject, body)

    cur.execute("""
        INSERT INTO sensor_alerts
        (sensor_name, timestamp, alert_type, message)
        VALUES (%s,%s,%s,%s)
    """, (sensor, datetime.now(timezone.utc), status, body.strip()))


# ============================================================
# SCORING ENGINE (PROFILE + STABILITY FIXED)
# ============================================================

def score(f, ema, profile):
    """
    Core predictive scoring engine.

    Uses:
    - sensor personality profile
    - statistical drift signals
    - CRC instability
    - EMA smoothing
    """

    if not f:
        return None, "insufficient data"

    if f.get("sensor_failure"):
        return 0, "sensor failure"

    score = 100
    notes = []

    # EMA smoothing (system memory influence)
    if ema is not None:
        score = (score * 0.7) + (float(ema) * 0.3)

    environmental_change = f.get("environmental_change", False)
    peer_outlier = f.get("peer_outlier", False)

    if peer_outlier:
        score -= 35
        notes.append("peer outlier")

    # Variance check (profile-aware). High variance during a broad greenhouse
    # ramp is usually weather/actuator behavior, not sensor degradation.
    if f["variance"] > profile["normal_variance"] * profile["noise_tolerance"]:
        if environmental_change and not peer_outlier:
            notes.append("environmental variance")
        else:
            score -= 20
            notes.append("high noise")

    # Drift checks (profile-aware). Temperature drift alone is not a sensor
    # fault in a greenhouse; it becomes suspicious only without environmental
    # peer context or other failure signals.
    if f["drift_short"] > 0.8 * profile["drift_sensitivity"]:
        if environmental_change and not peer_outlier:
            notes.append("environmental short trend")
        else:
            score -= 5
            notes.append("short temperature trend")

    if f["drift_long"] > 1.2 * profile["drift_sensitivity"]:
        if environmental_change and not peer_outlier:
            notes.append("environmental long trend")
        else:
            score -= 5
            notes.append("long temperature trend")

    # Range validation only applies when sensor_profile defines expected bounds.
    if profile["expected_min"] is not None and f["median"] < profile["expected_min"]:
        score -= 10
        notes.append("below expected range")

    if profile["expected_max"] is not None and f["median"] > profile["expected_max"]:
        score -= 10
        notes.append("above expected range")

    # CRC sensitivity
    if f["crc_rate"] > 0.3 * profile["crc_sensitivity"]:
        score -= 25
        notes.append("crc instability")

    if f.get("invalid_readings"):
        score -= min(50, 25 + int(f["invalid_ratio"] * 50))
        notes.append("ds18b20 sentinel values")

    if f.get("flatline"):
        score -= 35
        notes.append("flatline")

    return max(0, score), ", ".join(notes) or "ok"


# ============================================================
# DECISION ENGINE (UNIFIED + HYSTERESIS FIXED)
# ============================================================

def decide(new_score, prev_status, profile):
    """
    Converts health score into operational state.

    Now profile-aware to reduce false transitions and sensor-specific noise.
    """

    if new_score is None:
        return "INSUFFICIENT_DATA"

    # Profile-adjusted thresholds (future extensibility hook)
    high = 90
    mid = 70
    low = 50

    # Hysteresis: prevents status flickering
    if new_score >= high:
        return "HEALTHY"

    if new_score >= mid:
        if prev_status == "CRITICAL":
            return "DEGRADED"
        return "STABLE"

    if new_score >= low:
        return "DEGRADED"

    return "CRITICAL"


# ============================================================
# STATE UPDATE (EMA MEMORY)
# ============================================================

def update_state(cur, sensor, score_value, status):
    """
    Persists sensor memory and EMA smoothing.
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
        """, (sensor, status, score_value, score_value))
        return

    last_status, ema = row

    ema_base = float(ema) if ema is not None else float(score_value)
    ema = (ema_base * 0.8) + (float(score_value) * 0.2)

    # Recovery detection (stateful improvement)
    if last_status in ["DEGRADED", "CRITICAL"] and score_value >= 85:
        status = "RECOVERED"

    if status != last_status:
        cur.execute("""
            UPDATE sensor_state
            SET last_status=%s,
                last_health=%s,
                ema_health=%s,
                last_change_time=NOW()
            WHERE sensor_name=%s
        """, (status, score_value, ema, sensor))
    else:
        cur.execute("""
            UPDATE sensor_state
            SET last_status=%s,
                last_health=%s,
                ema_health=%s
            WHERE sensor_name=%s
        """, (status, score_value, ema, sensor))


# ============================================================
# MAIN EXECUTION LOOP
# ============================================================

def main():

    con = db()
    cur = con.cursor()

    # Discover sensors dynamically from diagnostics table
    cur.execute("SELECT DISTINCT sensor_name FROM sensor_diagnostics")
    sensors = [r[0] for r in cur.fetchall()]

    now = datetime.now(timezone.utc)

    profiles = {sensor: get_sensor_profile(cur, sensor) for sensor in sensors}
    feature_map = {sensor: features(cur, sensor) for sensor in sensors}

    for sensor in sensors:
        feature_map[sensor] = add_peer_context(
            sensor,
            profiles[sensor],
            feature_map[sensor],
            profiles,
            feature_map,
        )

    for sensor in sensors:

        profile = profiles[sensor]
        f = feature_map[sensor]

        cur.execute("""
            SELECT last_status, ema_health
            FROM sensor_state
            WHERE sensor_name=%s
        """, (sensor,))
        prev = cur.fetchone()

        prev_status = prev[0] if prev else None
        ema = prev[1] if prev else None

        health, notes = score(f, ema, profile)
        status = decide(health, prev_status, profile)
        stored_health = health if health is not None else 0

        conf = confidence(f)

        # Persist health record
        cur.execute("""
            INSERT INTO sensor_health
            (sensor_name, timestamp, health_score, status,
             crc_rate, variance, drift_short, drift_long,
             confidence, notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            sensor,
            now,
            stored_health,
            status,
            f["crc_rate"] if f else 0,
            f["variance"] if f else 0,
            f["drift_short"] if f else 0,
            f["drift_long"] if f else 0,
            conf,
            notes
        ))

        if health is None:
            continue

        update_state(cur, sensor, stored_health, status)

        # External alerting (restored + controlled)
        if status in ["DEGRADED", "CRITICAL", "RECOVERED"]:
            alert(cur, sensor, status, stored_health)

    con.close()


if __name__ == "__main__":
    main()
