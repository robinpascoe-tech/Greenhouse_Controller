#!/usr/bin/env python3

############################################################################
# Greenhouse Sensor Controller (v3.3.1 Compatible Ingestion Layer)
############################################################################
# Produces:
# - sensor_diagnostics (FULL coverage, even failures)
# - currenttemp (clean operational values)
#
# Designed to fully support sensor_health v3.3.1 predictive engine.
############################################################################

import time
import logging
import configparser
from logging.handlers import RotatingFileHandler
from decimal import Decimal
from datetime import datetime, timezone

import pymysql


# ============================================================
# LOGGING
# ============================================================

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


# ============================================================
# SENSOR MAP (cached paths)
# ============================================================

SENSORS = {
    "FrontTemp": "/sys/bus/w1/devices/28-0315018710ff/w1_slave",
    "BackTemp": "/sys/bus/w1/devices/28-04150123f0ff/w1_slave",
    "PiTemp": "/sys/bus/w1/devices/28-031515b5faff/w1_slave",
    "OutsideTemp": "/sys/bus/w1/devices/28-0215036e59ff/w1_slave",
    "WoodstoveTemp": "/sys/bus/w1/devices/28-031504bcbfff/w1_slave"
}


# ============================================================
# HELPERS
# ============================================================

TWOPLACES = Decimal("0.01")


def d(x):
    return Decimal(str(x)).quantize(TWOPLACES)


def to_f(c):
    return d((c * 9 / 5) + 32)


# ============================================================
# SENSOR READ (HARDENED + v3.3.1 SAFE)
# ============================================================

def read_sensor(sensor_name, path):

    readings = []
    crc_failures = 0
    attempts = 0

    start_time = time.monotonic()

    while len(readings) < 5:

        attempts += 1

        if attempts > 20:
            logger.error(f"{sensor_name} exceeded max attempts")
            return {
                "ok": False,
                "reason": "max_attempts",
                "avg": None,
                "median": None,
                "crc_failures": crc_failures,
                "raw": readings
            }

        try:
            with open(path) as f:
                text = f.read()
        except Exception as e:
            logger.error(f"{sensor_name} file error: {e}")
            return {
                "ok": False,
                "reason": "file_error",
                "avg": None,
                "median": None,
                "crc_failures": crc_failures,
                "raw": readings
            }

        lines = text.split("\n")

        # CRC validation
        if not lines or "YES" not in lines[0]:
            crc_failures += 1
            time.sleep(0.1)
            continue

        try:
            raw = lines[1].split(" ")[9]
            temp = float(raw[2:]) / 1000.0
        except (IndexError, ValueError):
            continue

        # reject invalid sensor spikes
        if temp == 85.0 or temp < -50 or temp > 100:
            continue

        readings.append(temp)
        time.sleep(0.1)

    duration = time.monotonic() - start_time

    readings.sort()

    median = readings[len(readings)//2]

    # trimmed mean (removes outliers)
    trimmed = readings[1:-1]
    avg = sum(trimmed) / len(trimmed)

    stale = len(set(readings)) == 1

    logger.info(
        f"{sensor_name} time={duration:.3f}s "
        f"raw={readings} median={median:.2f} avg={avg:.2f}"
    )

    if stale:
        logger.warning(f"{sensor_name} appears STALE")

    return {
        "ok": True,
        "avg": avg,
        "median": median,
        "crc_failures": crc_failures,
        "raw": readings
    }


# ============================================================
# DB CONNECTION
# ============================================================

config = configparser.ConfigParser()
config.read("/home/pi/py3refactor/greenhouse.conf")

try:
    DB_HOST = config["database"]["host"]
    DB_USER = config["database"]["user"]
    DB_PASSWORD = config["database"]["password"]
    DB_NAME = config["database"]["database"]
except Exception:
    DB_HOST = "localhost"
    DB_USER = "root"
    DB_PASSWORD = "change_this_password"
    DB_NAME = "greenhouse"


def db_connect():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.Cursor,
        connect_timeout=5,
        autocommit=False
    )


# ============================================================
# DIAGNOSTICS WRITER (v3.3.1 CONTRACT SAFE)
# ============================================================

def write_sensor_diagnostics(cur, timestamp, name, result):
    """
    Always writes a row to ensure health engine has full visibility.

    EVEN FAILED SENSORS ARE RECORDED.
    This is critical for predictive failure detection.
    """

    if result is None:
        result = {
            "ok": False,
            "avg": None,
            "median": None,
            "crc_failures": -1,
            "raw": []
        }

    raw_values = result.get("raw") or []
    raw = ",".join(str(x) for x in raw_values) if raw_values else "FAIL"

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
            d(result.get("median")) if result.get("median") is not None else None,
            d(result.get("avg")) if result.get("avg") is not None else None,
            result.get("crc_failures", 0),
            "ok" if result.get("ok") else "FAILED"
        )
    )


# ============================================================
# MAIN
# ============================================================

def main():

    con = None

    try:
        con = db_connect()
        cur = con.cursor()

        results = {}

        # IMPORTANT: timestamp must be defined BEFORE loop (fixes previous bug)
        timestamp = datetime.now(timezone.utc)

        # =====================================================
        # SENSOR ACQUISITION LOOP
        # =====================================================

        for name, path in SENSORS.items():

            start = time.monotonic()
            r = read_sensor(name, path)
            duration = time.monotonic() - start

            write_sensor_diagnostics(cur, timestamp, name, r)

            if r and r.get("ok"):
                results[name] = r
                logger.info(f"{name} OK in {duration:.3f}s")
            else:
                logger.error(f"{name} FAILED")

        inside = []

        # =====================================================
        # CURRENTTEMP UPDATE (OPERATIONAL VALUES ONLY)
        # =====================================================

        for name in ["FrontTemp", "BackTemp"]:
            if name in results:
                c = d(results[name]["avg"])
                f = to_f(c)

                inside.append(c)

                cur.execute(
                    """
                    UPDATE currenttemp
                    SET temperature=%s,
                        temperatureF=%s,
                        timestamp=%s
                    WHERE Name=%s
                    """,
                    (c, f, timestamp, name)
                )

        if inside:
            avg_c = d(sum(inside) / len(inside))
            avg_f = to_f(avg_c)

            cur.execute(
                """
                UPDATE currenttemp
                SET temperature=%s,
                    temperatureF=%s,
                    timestamp=%s
                WHERE Name=%s
                """,
                (avg_c, avg_f, timestamp, "AverageInsideTemp")
            )

        # =====================================================
        # OTHER SENSORS
        # =====================================================

        for name in ["PiTemp", "OutsideTemp", "WoodstoveTemp"]:
            if name in results:
                c = d(results[name]["avg"])
                f = to_f(c)

                cur.execute(
                    """
                    UPDATE currenttemp
                    SET temperature=%s,
                        temperatureF=%s,
                        timestamp=%s
                    WHERE Name=%s
                    """,
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
