#!/usr/bin/env python3

############################################################################
# Greenhouse Sensor Controller (Production Hardened Version)
############################################################################
# This script reads from multiple DS18B20 temperature sensors, performs
# CRC checks, discards outliers, and writes results to a MySQL database.
# It includes robust error handling, logging, and diagnostics for long-term
# tracking of sensor performance.
# Note: This is a production-hardened version with optimizations and
# improvements based on real-world usage and testing.
############################################################################
# Run from cron using flock -n /tmp/greenhouse.lock timeout 45s python3 /home/pi/greenhouse.py
# This ensures only one instance runs at a time and prevents hanging.
############################################################################

import time
import logging
from logging.handlers import RotatingFileHandler
from decimal import Decimal
from datetime import datetime, timezone

import pymysql


# ============================================================================
# LOGGING
# ============================================================================

LOG_FILE = "/home/pi/py3refactor/greenhouse_sensors.log"

logger = logging.getLogger("greenhouse")
logger.setLevel(logging.INFO)

handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=500000,
    backupCount=5
)

handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s"
))

logger.addHandler(handler)


# ============================================================================
# SENSOR PATH CACHE (HARDWARE OPTIMIZATION)
# ============================================================================

SENSORS = {
    "FrontTemp": "/sys/bus/w1/devices/28-0315018710ff/w1_slave",
    "BackTemp": "/sys/bus/w1/devices/28-04150123f0ff/w1_slave",
    "PiTemp": "/sys/bus/w1/devices/28-031515b5faff/w1_slave",
    "OutsideTemp": "/sys/bus/w1/devices/28-0215036e59ff/w1_slave",
    "WoodstoveTemp": "/sys/bus/w1/devices/28-031504bcbfff/w1_slave"
}


# ============================================================================
# HELPERS
# ============================================================================

TWOPLACES = Decimal("0.01")


def d(x):
    return Decimal(x).quantize(TWOPLACES)


def to_f(c):
    return d((c * 9 / 5) + 32)


# ============================================================================
# SENSOR READ FUNCTION (HARDENED)
# ============================================================================

def read_sensor(sensor_name, path):

    readings = []
    crc_failures = 0
    attempts = 0

    start_time = time.monotonic()

    while len(readings) < 5:

        attempts += 1

        if attempts > 20:
            logger.error(f"{sensor_name} exceeded max attempts")
            return None

        try:
            with open(path) as f:
                text = f.read()

        except Exception as e:
            logger.error(f"{sensor_name} file error: {e}")
            return None

        lines = text.split("\n")

        # CRC check
        if "YES" not in lines[0]:
            crc_failures += 1
            time.sleep(0.1)
            continue

        try:
            raw = lines[1].split(" ")[9]
            temp = float(raw[2:]) / 1000.0
        except:
            continue

        # discard bad values
        if temp == 85.0 or temp < -50 or temp > 100:
            continue

        readings.append(temp)
        time.sleep(0.1)

    duration = time.monotonic() - start_time

    readings.sort()

    median = readings[len(readings)//2]
    trimmed = readings[1:-1]

    avg = sum(trimmed) / len(trimmed)

    # stale detection (simple)
    stale = len(set(readings)) == 1

    logger.info(
        f"{sensor_name} time={duration:.3f}s "
        f"raw={readings} median={median:.2f} avg={avg:.2f}"
    )

    if stale:
        logger.warning(f"{sensor_name} appears STALE")

    return {
        "avg": avg,
        "median": median,
        "ok": True,
        "crc_failures": crc_failures,
        "raw": readings
    }


# ============================================================================
# DATABASE
# ============================================================================

def db_connect():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="change_this_password",
        database="greenhouse",
        cursorclass=pymysql.cursors.Cursor,
        autocommit=False
    )

# ============================================================================
# Write Sensor Diagnostics (for long-term tracking).
# ============================================================================

def write_sensor_diagnostics(cur, timestamp, name, result):
    """
    Writes per-sensor diagnostics to SQL for long-term tracking.
    """

    if not result:
        return

    raw = ",".join(str(x) for x in result["raw"])

    cur.execute(
        """
        INSERT INTO sensor_diagnostics
        (sensor_name, timestamp, raw_values, median, average, crc_failures, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            name,
            timestamp,
            raw,
            d(result["median"]),
            d(result["avg"]),
            result.get("crc_failures", 0),
            "ok"
        )
    )

# ============================================================================
# MAIN
# ============================================================================

def main():

    con = None

    try:
        con = db_connect()
        cur = con.cursor()

        results = {}

        # ---------------- READ ALL SENSORS ----------------
        for name, path in SENSORS.items():
            start = time.monotonic()
            r = read_sensor(name, path)
            duration = time.monotonic() - start

            if r:
                results[name] = r
                write_sensor_diagnostics(cur, timestamp, name, r)
                logger.info(f"{name} read OK in {duration:.3f}s")
            else:
                logger.error(f"{name} FAILED")

        inside = []

        timestamp = datetime.now(timezone.utc)

        # ---------------- UPDATE CURRENT TABLE ----------------

        for name in ["FrontTemp", "BackTemp"]:
            if name in results:
                c = d(results[name]["avg"])
                f = to_f(c)

                inside.append(c)

                cur.execute(
                    "UPDATE currenttemp SET temperature=%s, temperatureF=%s, timestamp=%s WHERE Name=%s",
                    (c, f, timestamp, name)
                )

        if inside:
            avg_c = d(sum(inside) / len(inside))
            avg_f = to_f(avg_c)

            cur.execute(
                "UPDATE currenttemp SET temperature=%s, temperatureF=%s, timestamp=%s WHERE Name=%s",
                (avg_c, avg_f, timestamp, "AverageInsideTemp")
            )

        # ---------------- OTHER SENSORS ----------------

        for name in ["PiTemp", "OutsideTemp", "WoodstoveTemp"]:
            if name in results:
                c = d(results[name]["avg"])
                f = to_f(c)

                cur.execute(
                    "UPDATE currenttemp SET temperature=%s, temperatureF=%s, timestamp=%s WHERE Name=%s",
                    (c, f, timestamp, name)
                )

        con.commit()

        logger.info("DB commit successful")

    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        if con:
            con.rollback()

    finally:
        if con:
            con.close()


if __name__ == "__main__":
    main()
