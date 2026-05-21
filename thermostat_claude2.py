#!/usr/bin/env python3
#################################################################
# Greenhouse Controller v4.2
# Production Hardened / Direct Drop-In Replacement
#
# Created by: Robin Pascoe + iterative engineering refactor
#
# Version: 2026-05-20 v4.2
#
# PURPOSE
# -------
# Greenhouse environmental controller for Raspberry Pi.
#
# Controls:
#   - Heater
#   - Ventilation Fans
#   - Circulation Fan
#   - Rear Window
#   - Roof Window
#
# Uses:
#   - MySQL/MariaDB backend
#   - GPIO relay outputs
#   - DS18B20 sensor data from checksensors
#
# DESIGN GOALS
# ------------
# - Preserve original greenhouse behavior EXACTLY where safety critical
# - Preserve original window timings and sequencing
# - Preserve original hysteresis control logic
# - Preserve original override system
# - Preserve original schedule system
#
# IMPROVEMENTS
# ------------
# - Python 3 modernization
# - Robust logging
# - DB retry logic
# - Sensor stale detection
# - Name-keyed sensor model
# - Safer shutdown handling
# - Better diagnostics
#
#################################################################

import sys
import time
import functools
import logging
import logging.handlers
import configparser
from decimal import Decimal
from datetime import datetime, timezone

import pymysql as mdb

# ================================================================
# GPIO IMPORT
# ================================================================

try:
    from RPi import GPIO

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

except ImportError:
    from unittest import mock

    GPIO = mock.MagicMock()
    print("WARNING: RPi.GPIO not available. Running in MOCK mode.")


# ================================================================
# GPIO ASSIGNMENTS
# ================================================================

WINDOW_REVERSER_GPIO = 22
WINDOW_GPIO = 17

ROOF_REVERSER_GPIO = 9
ROOF_GPIO = 10

VENT_FAN_GPIO = 5
AUX_VENT_FAN_GPIO = 11

HEATER_GPIO = 19
CIRC_FAN_GPIO = 6

# Original unused outputs preserved intentionally.
# Even unused relays should always be forced LOW for safety.
UNUSED_GPIO_1 = 13
UNUSED_GPIO_2 = 26
UNUSED_GPIO_3 = 27


# ================================================================
# LOGGING
# ================================================================

LOG_FILENAME = "/home/pi/py3refactor/thermostat.log"

logger = logging.getLogger("GreenhouseController")
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter(
    "%(asctime)s %(levelname)-8s %(message)s"
)

file_handler = logging.handlers.RotatingFileHandler(
    LOG_FILENAME,
    maxBytes=5 * 1024 * 1024,
    backupCount=5
)

file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Also log warnings/errors to stderr for systemd/journalctl visibility.
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.WARNING)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)


# ================================================================
# DATABASE CONFIGURATION
# ================================================================

config = configparser.ConfigParser()
config.read("/home/pi/py3refactor/greenhouse.conf")

try:
    DB_HOST = config["database"]["host"]
    DB_USER = config["database"]["user"]
    DB_PASSWORD = config["database"]["password"]
    DB_NAME = config["database"]["database"]

except Exception:

    # Preserve original hardcoded fallback behavior.
    logger.warning(
        "Could not load greenhouse.conf. "
        "Using hardcoded DB fallback."
    )

    DB_HOST = "localhost"
    DB_USER = "root"
    DB_PASSWORD = "change_this_password"
    DB_NAME = "greenhouse"


# ================================================================
# SENSOR CONFIGURATION
# ================================================================

# Name-keyed sensor model.
# This removes dangerous dependence on SQL row ordering.

SENSOR_PRIORITY = [
    "AverageInsideTemp",
    "FrontTemp",
    "BackTemp"
]

MAX_SENSOR_AGE_SECONDS = 60


# ================================================================
# STATUS CACHE
# ================================================================

# Used for status_log change detection.

last_status = {
    "heater": None,
    "fan": None,
    "circfan": None,
    "window": None
}


# ================================================================
# DATABASE RETRY DECORATOR
# ================================================================

def db_retry(max_retries=5, delay=5):

    def decorator(func):

        @functools.wraps(func)
        def wrapper(*args, **kwargs):

            last_exception = None

            for attempt in range(1, max_retries + 1):

                try:
                    return func(*args, **kwargs)

                except mdb.Error as e:

                    last_exception = e

                    logger.warning(
                        "DB error in %s attempt %d/%d: %s",
                        func.__name__,
                        attempt,
                        max_retries,
                        e
                    )

                    time.sleep(delay)

            raise last_exception

        return wrapper

    return decorator


# ================================================================
# DATABASE CONNECTION
# ================================================================

@db_retry()
def get_db_connection():

    return mdb.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        connect_timeout=5,
        autocommit=False
    )


# ================================================================
# GPIO INITIALIZATION
# ================================================================

def setup_gpio():
    """
    Initialize ALL outputs to LOW safe state.

    Original controller intentionally forced all GPIO outputs LOW
    during startup to prevent accidental relay activation.
    """

    outputs = [
        WINDOW_REVERSER_GPIO,
        WINDOW_GPIO,
        ROOF_REVERSER_GPIO,
        ROOF_GPIO,
        VENT_FAN_GPIO,
        AUX_VENT_FAN_GPIO,
        HEATER_GPIO,
        CIRC_FAN_GPIO,
        UNUSED_GPIO_1,
        UNUSED_GPIO_2,
        UNUSED_GPIO_3
    ]

    for pin in outputs:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)

    logger.info("GPIO initialized to safe LOW state.")

    # Preserve original startup behavior:
    # ALWAYS close windows at startup as safety precaution.

    close_windows()


# ================================================================
# WINDOW CONTROL
# ================================================================

def open_windows():
    """
    Open rear window then roof window.

    Timing values intentionally preserved EXACTLY from original
    controller due to motor/mechanical requirements.
    """

    logger.info("Opening windows.")

    # Rear window first.
    GPIO.output(WINDOW_REVERSER_GPIO, GPIO.HIGH)
    time.sleep(0.5)

    GPIO.output(WINDOW_GPIO, GPIO.HIGH)
    time.sleep(35)

    GPIO.output(WINDOW_GPIO, GPIO.LOW)
    GPIO.output(WINDOW_REVERSER_GPIO, GPIO.LOW)

    # Roof window.
    GPIO.output(ROOF_REVERSER_GPIO, GPIO.HIGH)
    time.sleep(0.5)

    GPIO.output(ROOF_GPIO, GPIO.HIGH)
    time.sleep(14)

    GPIO.output(ROOF_GPIO, GPIO.LOW)
    GPIO.output(ROOF_REVERSER_GPIO, GPIO.LOW)

    update_window_status(1)


def close_windows():
    """
    Close roof and rear windows.

    Original sequencing preserved intentionally.
    """

    logger.info("Closing windows.")

    GPIO.output(WINDOW_REVERSER_GPIO, GPIO.LOW)
    GPIO.output(ROOF_REVERSER_GPIO, GPIO.LOW)

    time.sleep(0.5)

    GPIO.output(WINDOW_GPIO, GPIO.HIGH)
    time.sleep(24)

    GPIO.output(ROOF_GPIO, GPIO.HIGH)
    time.sleep(16)

    GPIO.output(WINDOW_GPIO, GPIO.LOW)
    GPIO.output(ROOF_GPIO, GPIO.LOW)

    update_window_status(0)


# ================================================================
# EMERGENCY SHUTDOWN
# ================================================================

def shutdownnow():
    """
    Emergency safe shutdown.

    Original safety behavior preserved:
    - all outputs LOW
    - windows closed
    - GPIO cleanup
    """

    logger.error("EMERGENCY SHUTDOWN INITIATED")

    try:

        GPIO.output(VENT_FAN_GPIO, GPIO.LOW)
        GPIO.output(AUX_VENT_FAN_GPIO, GPIO.LOW)

        GPIO.output(CIRC_FAN_GPIO, GPIO.LOW)

        GPIO.output(HEATER_GPIO, GPIO.LOW)

        GPIO.output(UNUSED_GPIO_1, GPIO.LOW)
        GPIO.output(UNUSED_GPIO_2, GPIO.LOW)
        GPIO.output(UNUSED_GPIO_3, GPIO.LOW)

        close_windows()

    except Exception:
        logger.exception("Error during emergency shutdown.")

    finally:

        GPIO.cleanup()

    sys.exit(1)


# ================================================================
# STATUS DATABASE HELPERS
# ================================================================

@db_retry()
def update_status(query, values):

    con = None

    try:

        con = get_db_connection()

        with con.cursor() as cur:
            cur.execute(query, values)

        con.commit()

    finally:

        if con:
            con.close()


def update_window_status(state):

    try:

        update_status(
            "UPDATE status SET window=%s WHERE id=1",
            (state,)
        )

    except Exception:
        logger.exception("Failed updating window status.")


@db_retry()
def log_status_if_changed():
    """
    Preserve original status_log behavior.

    Only insert rows when actuator states change.
    """

    global last_status

    con = None

    try:

        con = get_db_connection()

        with con.cursor() as cur:

            cur.execute(
                "SELECT heater, fan, circfan, window "
                "FROM status WHERE id=1"
            )

            row = cur.fetchone()

            current = {
                "heater": int(row[0]),
                "fan": int(row[1]),
                "circfan": int(row[2]),
                "window": int(row[3])
            }

            if current == last_status:
                return

            last_status = current

            cur.execute(
                """
                INSERT INTO status_log
                (heater, fan, circfan, window)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    current["heater"],
                    current["fan"],
                    current["circfan"],
                    current["window"]
                )
            )

        con.commit()

    finally:

        if con:
            con.close()


# ================================================================
# SENSOR LOADING
# ================================================================

@db_retry()
def get_sensor_data():
    """
    Load sensors into name-keyed structure.

    Avoids dangerous SQL row ordering assumptions.
    """

    con = None

    try:

        con = get_db_connection()

        with con.cursor() as cur:

            cur.execute(
                "SELECT Name, temperature, timestamp "
                "FROM currenttemp"
            )

            rows = cur.fetchall()

        sensors = {}

        now = datetime.now(timezone.utc)

        for row in rows:

            name = row[0]
            temp = Decimal(str(row[1]))

            timestamp = row[2]

            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(
                    tzinfo=timezone.utc
                )

            age = (now - timestamp).total_seconds()

            sensors[name] = {
                "temp": temp,
                "age": age
            }

        return sensors

    finally:

        if con:
            con.close()


# ================================================================
# SENSOR POLICY ENGINE
# ================================================================

def select_working_temperature(sensors):
    """
    Choose best available temperature source.

    Priority:
        1. AverageInsideTemp
        2. FrontTemp
        3. BackTemp

    Only accept fresh readings.
    """

    for sensor_name in SENSOR_PRIORITY:

        if sensor_name not in sensors:
            continue

        sensor = sensors[sensor_name]

        if sensor["age"] <= MAX_SENSOR_AGE_SECONDS:

            if sensor_name != "AverageInsideTemp":
                logger.warning(
                    "Using fallback sensor: %s",
                    sensor_name
                )

            return sensor["temp"]

    logger.error("No valid fresh sensors available.")

    shutdownnow()


# ================================================================
# SCHEDULE SETTINGS
# ================================================================

@db_retry()
def get_schedule_settings():

    con = None

    try:

        con = get_db_connection()

        with con.cursor() as cur:

            cur.execute(
                """
                SELECT
                    hightemp,
                    lowtemp,
                    hightemprange,
                    lowtemprange,
                    windowtemp,
                    windowtemprange,
                    circfan,
                    endtime
                FROM settings
                """
            )

            rows = cur.fetchall()

        now_time = datetime.now().time()

        for row in rows:

            end_time = row[7]

            if now_time < end_time:

                return {
                    "hightemp": Decimal(str(row[0])),
                    "lowtemp": Decimal(str(row[1])),
                    "hightemprange": Decimal(str(row[2])),
                    "lowtemprange": Decimal(str(row[3])),
                    "windowtemp": Decimal(str(row[4])),
                    "windowtemprange": Decimal(str(row[5])),
                    "circfan": int(row[6])
                }

        raise RuntimeError("No valid schedule found.")

    finally:

        if con:
            con.close()


# ================================================================
# OVERRIDES
# ================================================================

@db_retry()
def get_override_settings():

    con = None

    try:

        con = get_db_connection()

        with con.cursor() as cur:

            cur.execute(
                """
                SELECT
                    windowoverride,
                    windowexpire,
                    fanoverride,
                    fanexpire
                FROM overrides
                """
            )

            row = cur.fetchone()

        now = datetime.now(timezone.utc)

        window_override = (
            int(row[0]) == 1 and
            now < row[1].replace(tzinfo=timezone.utc)
        )

        fan_override = (
            int(row[2]) == 1 and
            now < row[3].replace(tzinfo=timezone.utc)
        )

        return {
            "window": window_override,
            "fan": fan_override
        }

    finally:

        if con:
            con.close()


# ================================================================
# WINDOW STATE
# ================================================================

@db_retry()
def get_window_state():

    con = None

    try:

        con = get_db_connection()

        with con.cursor() as cur:

            cur.execute(
                "SELECT window FROM status WHERE id=1"
            )

            row = cur.fetchone()

            return int(row[0])

    finally:

        if con:
            con.close()


# ================================================================
# CONTROL FUNCTIONS
# ================================================================

def heater_control(current_temp, low_temp, low_range):

    half = low_range / 2

    lower = low_temp - half
    upper = low_temp + half

    if current_temp <= lower:

        GPIO.output(HEATER_GPIO, GPIO.HIGH)

        update_status(
            "UPDATE status SET heater=%s WHERE id=1",
            (1,)
        )

        logger.info("Heater ON")

    elif current_temp >= upper:

        GPIO.output(HEATER_GPIO, GPIO.LOW)

        update_status(
            "UPDATE status SET heater=%s WHERE id=1",
            (0,)
        )

        logger.info("Heater OFF")


def ventilation_control(
    current_temp,
    high_temp,
    high_range,
    override
):

    half = high_range / 2

    lower = high_temp - half
    upper = high_temp + half

    if override:
        fan_on = True

    elif current_temp >= upper:
        fan_on = True

    elif current_temp <= lower:
        fan_on = False

    else:
        return

    if fan_on:

        GPIO.output(VENT_FAN_GPIO, GPIO.HIGH)
        time.sleep(1)

        GPIO.output(AUX_VENT_FAN_GPIO, GPIO.HIGH)

        logger.info("Ventilation fans ON")

    else:

        GPIO.output(VENT_FAN_GPIO, GPIO.LOW)
        GPIO.output(AUX_VENT_FAN_GPIO, GPIO.LOW)

        logger.info("Ventilation fans OFF")

    update_status(
        "UPDATE status SET fan=%s WHERE id=1",
        (1 if fan_on else 0,)
    )


def circulation_control(enabled):

    GPIO.output(
        CIRC_FAN_GPIO,
        GPIO.HIGH if enabled else GPIO.LOW
    )

    update_status(
        "UPDATE status SET circfan=%s WHERE id=1",
        (1 if enabled else 0,)
    )


def window_control(
    current_temp,
    target_temp,
    temp_range,
    override
):

    half = temp_range / 2

    lower = target_temp - half
    upper = target_temp + half

    current_state = get_window_state()

    if override:
        should_open = True

    elif current_temp >= upper:
        should_open = True

    elif current_temp <= lower:
        should_open = False

    else:
        return

    if should_open and current_state == 0:
        open_windows()

    elif not should_open and current_state == 1:
        close_windows()


# ================================================================
# MAIN LOOP
# ================================================================

def main():

    logger.info("Greenhouse Controller v4.2 starting.")

    setup_gpio()

    # Preserve original startup DB reset behavior.
    update_status(
        """
        UPDATE status
        SET heater=0, fan=0, circfan=0, window=0
        WHERE id=1
        """,
        ()
    )

    time.sleep(5)

    try:

        while True:

            sensors = get_sensor_data()

            current_temp = select_working_temperature(
                sensors
            )

            settings = get_schedule_settings()

            overrides = get_override_settings()

            ventilation_control(
                current_temp,
                settings["hightemp"],
                settings["hightemprange"],
                overrides["fan"]
            )

            heater_control(
                current_temp,
                settings["lowtemp"],
                settings["lowtemprange"]
            )

            circulation_control(
                settings["circfan"]
            )

            window_control(
                current_temp,
                settings["windowtemp"],
                settings["windowtemprange"],
                overrides["window"]
            )

            log_status_if_changed()

            time.sleep(20)

    except KeyboardInterrupt:

        logger.info("KeyboardInterrupt received.")
        shutdownnow()

    except Exception:

        logger.exception("Fatal controller exception.")
        shutdownnow()


# ================================================================
# ENTRY POINT
# ================================================================

if __name__ == "__main__":
    main()