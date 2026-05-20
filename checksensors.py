#!/usr/bin/env python3

############################################################################
# Check Sensors (Modernized Python 3 Version)
#
# Original Author: Robin Pascoe
# Modernized:
#   - Python 3 compatible
#   - PyMySQL instead of MySQLdb
#   - Rotating log files for cron-safe operation
#   - Timezone-aware UTC timestamps
#   - Improved DS18B20 filtering and retry logic
#   - 6 reads, discard high/low outliers, average remaining 4
#
# Functional behavior preserved from original script except:
#   1. Fixed FrontTemp/BackTemp SQL swap bug
#   2. Improved sensor validation/filtering
#   3. Logging replaces print statements
############################################################################

import sys
import time
import subprocess
import logging
from logging.handlers import RotatingFileHandler
from decimal import Decimal
from datetime import datetime, timezone

import pymysql


# ============================================================================
# LOGGING SETUP
# ============================================================================

LOG_FILE = "/var/log/greenhouse_sensors.log"

logger = logging.getLogger("greenhouse_sensors")
logger.setLevel(logging.INFO)

handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=500000,      # 500 KB
    backupCount=5
)

formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s"
)

handler.setFormatter(formatter)
logger.addHandler(handler)


# ============================================================================
# LOAD KERNEL MODULES
# ============================================================================

subprocess.run(["modprobe", "w1-gpio"], check=False)
subprocess.run(["modprobe", "w1-therm"], check=False)


# ============================================================================
# SENSOR IDS
# ============================================================================

FrontTempSensor = '28-0315018710ff'
BackTempSensor = '28-04150123f0ff'
PiTempSensor = '28-031515b5faff'
OutsideTempSensor = '28-0215036e59ff'
WoodStoveTempSensor = '28-031504bcbfff'


# ============================================================================
# DECIMAL HELPERS
# ============================================================================

TWOPLACES = Decimal("0.01")


def d(val):
    """Round Decimal to 2 places."""
    return Decimal(val).quantize(TWOPLACES)


def to_f(celsius):
    """Convert Celsius to Fahrenheit."""
    return d((celsius * 9 / 5) + 32)


# ============================================================================
# SENSOR READ FUNCTION
# ============================================================================

def getavgtemp(sensor_id):
    """
    Read DS18B20 temperature sensor 6 times.
    Discard:
        - highest value
        - lowest value
    Average remaining 4 readings.

    Additional protections:
        - discard 85.0C glitch readings
        - discard impossible temperatures
        - retry CRC failures properly

    Returns:
        [temperature, status]

        status:
            1 = success
            0 = failure
    """

    temperatures = []

    max_crc_failures = 5
    crc_failures = 0

    max_total_attempts = 20
    total_attempts = 0

    while len(temperatures) < 6:

        total_attempts += 1

        if total_attempts > max_total_attempts:
            logger.warning(
                f"Sensor {sensor_id} exceeded max attempts"
            )
            return [85, 0]

        try:
            with open(
                f"/sys/bus/w1/devices/{sensor_id}/w1_slave",
                "r"
            ) as f:
                text = f.read()

        except Exception as e:
            logger.error(
                f"Sensor read error {sensor_id}: {e}"
            )
            return [85, 0]

        lines = text.split("\n")

        # --------------------------------------------------------------------
        # CRC CHECK
        # --------------------------------------------------------------------

        if "YES" not in lines[0]:

            crc_failures += 1

            logger.warning(
                f"CRC failure for sensor {sensor_id} "
                f"(failure {crc_failures}/{max_crc_failures})"
            )

            if crc_failures >= max_crc_failures:
                logger.error(
                    f"Sensor {sensor_id} exceeded CRC retry limit"
                )
                return [85, 0]

            time.sleep(0.1)
            continue

        # CRC success resets counter
        crc_failures = 0

        # --------------------------------------------------------------------
        # PARSE TEMPERATURE
        # --------------------------------------------------------------------

        try:
            second_line = lines[1]
            temp_raw = second_line.split(" ")[9]
            temp_c = float(temp_raw[2:]) / 1000.0

        except Exception as e:
            logger.error(
                f"Temperature parse error {sensor_id}: {e}"
            )
            continue

        # --------------------------------------------------------------------
        # DISCARD KNOWN BAD VALUES
        # --------------------------------------------------------------------

        # DS18B20 startup glitch
        if temp_c == 85.0:

            logger.warning(
                f"Discarded 85.0C glitch reading "
                f"from sensor {sensor_id}"
            )

            continue

        # Physically impossible values
        if temp_c < -50 or temp_c > 100:

            logger.warning(
                f"Discarded out-of-range reading "
                f"{temp_c:.2f}C from sensor {sensor_id}"
            )

            continue

        temperatures.append(temp_c)

        time.sleep(0.05)

    # ------------------------------------------------------------------------
    # TRIM OUTLIERS
    # ------------------------------------------------------------------------

    temperatures.sort()

    logger.info(
        f"Sensor {sensor_id} raw readings: "
        f"{[round(t, 3) for t in temperatures]}"
    )

    # Drop lowest and highest values
    trimmed = temperatures[1:-1]

    avg_temp = sum(trimmed) / len(trimmed)

    logger.info(
        f"Sensor {sensor_id} trimmed readings: "
        f"{[round(t, 3) for t in trimmed]} "
        f"average={avg_temp:.3f}"
    )

    return [avg_temp, 1]


# ============================================================================
# READ SENSOR VALUES
# ============================================================================

FrontTempC = getavgtemp(FrontTempSensor)
BackTempC = getavgtemp(BackTempSensor)
PiTempC = getavgtemp(PiTempSensor)
OutsideTempC = getavgtemp(OutsideTempSensor)
WoodStoveTempC = getavgtemp(WoodStoveTempSensor)

AvgTemps = []


# ============================================================================
# UTC TIMESTAMP (timezone-aware)
# ============================================================================

timestamp = datetime.now(timezone.utc)


# ============================================================================
# DATABASE UPDATE
# ============================================================================

con = None

try:

    con = pymysql.connect(
        host="localhost",
        user="root",
        password="change_this_password",
        database="greenhouse",
        cursorclass=pymysql.cursors.Cursor,
        autocommit=False
    )

    cur = con.cursor()

    # ------------------------------------------------------------------------
    # FRONT TEMP
    # ------------------------------------------------------------------------

    if FrontTempC[1] == 1:

        front_c = d(FrontTempC[0])
        front_f = to_f(front_c)

        AvgTemps.append(front_c)

        cur.execute(
            """
            UPDATE currenttemp
            SET temperature=%s,
                temperatureF=%s,
                timestamp=%s
            WHERE Name=%s
            """,
            (
                front_c,
                front_f,
                timestamp,
                "FrontTemp"
            )
        )

        logger.info("FrontTemp updated")

    # ------------------------------------------------------------------------
    # BACK TEMP
    # ------------------------------------------------------------------------

    if BackTempC[1] == 1:

        back_c = d(BackTempC[0])
        back_f = to_f(back_c)

        AvgTemps.append(back_c)

        cur.execute(
            """
            UPDATE currenttemp
            SET temperature=%s,
                temperatureF=%s,
                timestamp=%s
            WHERE Name=%s
            """,
            (
                back_c,
                back_f,
                timestamp,
                "BackTemp"
            )
        )

        logger.info("BackTemp updated")

    # ------------------------------------------------------------------------
    # PI TEMP
    # ------------------------------------------------------------------------

    if PiTempC[1] == 1:

        pi_c = d(PiTempC[0])
        pi_f = to_f(pi_c)

        # Intentionally NOT included in AvgTemps
        # Preserved from original logic

        cur.execute(
            """
            UPDATE currenttemp
            SET temperature=%s,
                temperatureF=%s,
                timestamp=%s
            WHERE Name=%s
            """,
            (
                pi_c,
                pi_f,
                timestamp,
                "PiTemp"
            )
        )

        logger.info("PiTemp updated")

    # ------------------------------------------------------------------------
    # AVERAGE INSIDE TEMP
    # ------------------------------------------------------------------------

    if AvgTemps:

        avg_c = d(sum(AvgTemps) / len(AvgTemps))
        avg_f = to_f(avg_c)

        cur.execute(
            """
            UPDATE currenttemp
            SET temperature=%s,
                temperatureF=%s,
                timestamp=%s
            WHERE Name=%s
            """,
            (
                avg_c,
                avg_f,
                timestamp,
                "AverageInsideTemp"
            )
        )

        logger.info("AverageInsideTemp updated")

    # ------------------------------------------------------------------------
    # OUTSIDE TEMP
    # ------------------------------------------------------------------------

    if OutsideTempC[1] == 1:

        outside_c = d(OutsideTempC[0])
        outside_f = to_f(outside_c)

        cur.execute(
            """
            UPDATE currenttemp
            SET temperature=%s,
                temperatureF=%s,
                timestamp=%s
            WHERE Name=%s
            """,
            (
                outside_c,
                outside_f,
                timestamp,
                "OutsideTemp"
            )
        )

        logger.info("OutsideTemp updated")

    # ------------------------------------------------------------------------
    # WOOD STOVE TEMP
    # ------------------------------------------------------------------------

    if WoodStoveTempC[1] == 1:

        wood_c = d(WoodStoveTempC[0])
        wood_f = to_f(wood_c)

        cur.execute(
            """
            UPDATE currenttemp
            SET temperature=%s,
                temperatureF=%s,
                timestamp=%s
            WHERE Name=%s
            """,
            (
                wood_c,
                wood_f,
                timestamp,
                "WoodstoveTemp"
            )
        )

        logger.info("WoodstoveTemp updated")

    con.commit()

    logger.info("Database commit successful")

# ============================================================================
# DATABASE ERRORS
# ============================================================================

except pymysql.MySQLError as e:

    logger.error(f"MySQL error: {e}")

    if con:
        con.rollback()

    sys.exit(1)

# ============================================================================
# GENERAL ERRORS
# ============================================================================

except Exception as e:

    logger.exception(f"Unexpected error: {e}")

    if con:
        con.rollback()

    sys.exit(1)

# ============================================================================
# CLEANUP
# ============================================================================

finally:

    if con:
        con.close()
