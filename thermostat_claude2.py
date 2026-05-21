#!/usr/bin/env python3
#################################################################
# Greenhouse Controller v4.3
#
# Direct drop-in replacement for the original controller.
#
# Preserves:
# - Original heater/fan/window hysteresis logic
# - Original schedule system
# - Original override system
# - Original window opening/closing timings
# - Original emergency shutdown window-closure behavior
# - Original status/status_log behavior
#
# Adds:
# - Name-keyed sensor model
# - Sensor fallback policy
# - In-memory short-cycle protection
# - Window reversal lockout
# - Dynamic hysteresis widening to reduce excessive cycling
#################################################################

import sys
import time
import functools
import logging
import logging.handlers
import configparser
from decimal import Decimal
from datetime import datetime, timezone, timedelta

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

# Preserved from original controller.
# These are intentionally driven LOW at startup and shutdown.
UNUSED_GPIO_1 = 13
UNUSED_GPIO_2 = 26
UNUSED_GPIO_3 = 27


# ================================================================
# LOGGING
# ================================================================

LOG_FILENAME = "/home/pi/py3refactor/thermostat.log"

logger = logging.getLogger("GreenhouseController")
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(asctime)s %(levelname)-8s %(message)s")

file_handler = logging.handlers.RotatingFileHandler(
    LOG_FILENAME,
    maxBytes=5 * 1024 * 1024,
    backupCount=5,
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

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
    logger.warning(
        "Could not load greenhouse.conf. Using hardcoded DB fallback."
    )
    DB_HOST = "localhost"
    DB_USER = "root"
    DB_PASSWORD = "change_this_password"
    DB_NAME = "greenhouse"


# ================================================================
# SENSOR POLICY
# ================================================================

SENSOR_PRIORITY = [
    "AverageInsideTemp",
    "FrontTemp",
    "BackTemp",
]

MAX_SENSOR_AGE_SECONDS = 60


# ================================================================
# SHORT-CYCLE / ANTI-CHATTER CONFIGURATION
# ================================================================

# These values protect relays, motors, and mechanical window actuators.
# They do NOT replace hysteresis; they only prevent rapid repeated transitions.

ACTUATOR_RULES = {
    "heater": {
        "min_on": 300,          # stay on at least 5 min before off
        "min_off": 120,         # stay off at least 2 min before on
        "warn_cycles": 6,       # transitions/hour before widening hysteresis
        "severe_cycles": 12,
        "warning_bonus": Decimal("1.0"),
        "severe_bonus": Decimal("2.0"),
    },
    "fan": {
        "min_on": 120,          # stay on at least 2 min
        "min_off": 60,          # stay off at least 1 min
        "warn_cycles": 10,
        "severe_cycles": 20,
        "warning_bonus": Decimal("1.0"),
        "severe_bonus": Decimal("2.0"),
    },
    "window": {
        "min_on": 300,          # minimum time between movements
        "min_off": 300,
        "warn_cycles": 4,
        "severe_cycles": 8,
        "warning_bonus": Decimal("1.0"),
        "severe_bonus": Decimal("2.0"),
    },
}

WINDOW_REVERSAL_LOCKOUT_SECONDS = 60
CYCLE_HISTORY_SECONDS = 3600


# In-memory state is intentionally used here.
# It is sufficient for this project and avoids extra SQL schema complexity.
ACTUATOR_STATE = {
    "heater": {
        "state": False,
        "last_change": 0.0,
        "changes": [],
    },
    "fan": {
        "state": False,
        "last_change": 0.0,
        "changes": [],
    },
    "window": {
        "state": False,          # False=closed, True=open
        "last_change": 0.0,
        "last_direction": None,  # "open" or "close"
        "changes": [],
    },
}


# ================================================================
# STATUS CACHE
# ================================================================

last_status = {
    "heater": None,
    "fan": None,
    "circfan": None,
    "window": None,
}


# ================================================================
# DATABASE HELPERS
# ================================================================

def db_retry(max_retries=5, delay=5):
    """Retry database operations before allowing the controller to fail safe."""
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
                        e,
                    )
                    time.sleep(delay)

            raise last_exception

        return wrapper

    return decorator


@db_retry()
def get_db_connection():
    return mdb.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        connect_timeout=5,
        autocommit=False,
    )


@db_retry()
def update_status(query, values):
    """Update the status table and commit immediately."""
    con = None
    try:
        con = get_db_connection()
        with con.cursor() as cur:
            cur.execute(query, values)
        con.commit()
    except Exception:
        if con:
            con.rollback()
        raise
    finally:
        if con:
            con.close()


def update_window_status(state):
    """Persist window state to the status table."""
    try:
        update_status(
            "UPDATE status SET window=%s WHERE id=1",
            (state,),
        )
    except Exception:
        logger.exception("Failed updating window status.")


@db_retry()
def log_status_if_changed():
    """Preserve original status_log behavior: log only when actuator state changes."""
    global last_status

    con = None
    try:
        con = get_db_connection()
        with con.cursor() as cur:
            cur.execute(
                "SELECT heater, fan, circfan, window FROM status WHERE id=1"
            )
            row = cur.fetchone()

            if not row:
                return

            current = {
                "heater": int(row[0]),
                "fan": int(row[1]),
                "circfan": int(row[2]),
                "window": int(row[3]),
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
                    current["window"],
                ),
            )

        con.commit()

    finally:
        if con:
            con.close()


# ================================================================
# ACTUATOR PROTECTION HELPERS
# ================================================================

def _prune_cycle_history(actuator):
    """Keep only recent actuator transitions for cycle-rate detection."""
    now = time.monotonic()
    ACTUATOR_STATE[actuator]["changes"] = [
        t for t in ACTUATOR_STATE[actuator]["changes"]
        if now - t <= CYCLE_HISTORY_SECONDS
    ]


def record_actuator_change(actuator, new_state):
    """Record actuator transition for short-cycle and dynamic hysteresis logic."""
    now = time.monotonic()

    ACTUATOR_STATE[actuator]["state"] = new_state
    ACTUATOR_STATE[actuator]["last_change"] = now
    ACTUATOR_STATE[actuator]["changes"].append(now)

    _prune_cycle_history(actuator)


def actuator_can_change(actuator, desired_state):
    """
    Enforce minimum ON/OFF durations.

    Emergency shutdown bypasses this function entirely.
    """
    current_state = ACTUATOR_STATE[actuator]["state"]

    if current_state == desired_state:
        return False

    rules = ACTUATOR_RULES[actuator]
    elapsed = time.monotonic() - ACTUATOR_STATE[actuator]["last_change"]

    if current_state is True and desired_state is False:
        if elapsed < rules["min_on"]:
            logger.info(
                "%s OFF blocked by min_on protection (%.0fs remaining)",
                actuator,
                rules["min_on"] - elapsed,
            )
            return False

    if current_state is False and desired_state is True:
        if elapsed < rules["min_off"]:
            logger.info(
                "%s ON blocked by min_off protection (%.0fs remaining)",
                actuator,
                rules["min_off"] - elapsed,
            )
            return False

    return True


def dynamic_hysteresis_range(actuator, base_range):
    """
    Dynamically widen hysteresis when excessive cycling is detected.

    Design decision:
    - Never shrink below configured DB range.
    - Only widen temporarily based on recent cycling.
    - This preserves schedule intent while protecting hardware.
    """
    _prune_cycle_history(actuator)

    cycles = len(ACTUATOR_STATE[actuator]["changes"])
    rules = ACTUATOR_RULES[actuator]

    base_range = Decimal(base_range)

    if cycles >= rules["severe_cycles"]:
        effective = base_range + rules["severe_bonus"]
        logger.warning(
            "%s severe cycling detected (%d/hr). "
            "Using widened hysteresis range %s.",
            actuator,
            cycles,
            effective,
        )
        return effective

    if cycles >= rules["warn_cycles"]:
        effective = base_range + rules["warning_bonus"]
        logger.warning(
            "%s elevated cycling detected (%d/hr). "
            "Using widened hysteresis range %s.",
            actuator,
            cycles,
            effective,
        )
        return effective

    return base_range


def window_direction_allowed(direction):
    """
    Prevent rapid window direction reversal.

    This protects timed motors, relays, and gear mechanisms.
    """
    state = ACTUATOR_STATE["window"]
    last_direction = state["last_direction"]

    if last_direction is None:
        return True

    if last_direction == direction:
        return True

    elapsed = time.monotonic() - state["last_change"]

    if elapsed < WINDOW_REVERSAL_LOCKOUT_SECONDS:
        logger.warning(
            "Window %s blocked by reversal lockout (%.0fs remaining).",
            direction,
            WINDOW_REVERSAL_LOCKOUT_SECONDS - elapsed,
        )
        return False

    return True


# ================================================================
# GPIO INITIALIZATION
# ================================================================

def setup_gpio():
    """Initialize all GPIO outputs to safe LOW state and close windows at startup."""
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
        UNUSED_GPIO_3,
    ]

    for pin in outputs:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)

    logger.info("GPIO initialized to safe LOW state.")

    # Original behavior preserved: close windows at startup.
    close_windows(force=True)


# ================================================================
# WINDOW CONTROL
# ================================================================

def open_windows(force=False):
    """
    Open rear window then roof window.

    Original timing preserved exactly:
    - rear window: 35s
    - roof window: 14s
    """
    if not force:
        if not actuator_can_change("window", True):
            return
        if not window_direction_allowed("open"):
            return

    logger.info("Opening windows.")

    GPIO.output(WINDOW_REVERSER_GPIO, GPIO.HIGH)
    time.sleep(0.5)

    GPIO.output(WINDOW_GPIO, GPIO.HIGH)
    time.sleep(35)

    GPIO.output(WINDOW_GPIO, GPIO.LOW)
    GPIO.output(WINDOW_REVERSER_GPIO, GPIO.LOW)

    GPIO.output(ROOF_REVERSER_GPIO, GPIO.HIGH)
    time.sleep(0.5)

    GPIO.output(ROOF_GPIO, GPIO.HIGH)
    time.sleep(14)

    GPIO.output(ROOF_GPIO, GPIO.LOW)
    GPIO.output(ROOF_REVERSER_GPIO, GPIO.LOW)

    ACTUATOR_STATE["window"]["last_direction"] = "open"
    record_actuator_change("window", True)

    update_window_status(1)


def close_windows(force=False):
    """
    Close roof and rear windows.

    Original timing preserved exactly:
    - rear/window close drive: 24s
    - roof close drive: 16s
    """
    if not force:
        if not actuator_can_change("window", False):
            return
        if not window_direction_allowed("close"):
            return

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

    ACTUATOR_STATE["window"]["last_direction"] = "close"
    record_actuator_change("window", False)

    update_window_status(0)


# ================================================================
# EMERGENCY SHUTDOWN
# ================================================================

def shutdownnow():
    """
    Emergency safe shutdown.

    Design decision:
    - Short-cycle protection is bypassed here.
    - Safety overrides hardware wear protection.
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

        close_windows(force=True)

    except Exception:
        logger.exception("Error during emergency shutdown.")

    finally:
        GPIO.cleanup()

    sys.exit(1)


# ================================================================
# SENSOR LOADING
# ================================================================

@db_retry()
def get_sensor_data():
    """Load currenttemp rows into a name-keyed dictionary."""
    con = None

    try:
        con = get_db_connection()

        with con.cursor() as cur:
            cur.execute("SELECT Name, temperature, timestamp FROM currenttemp")
            rows = cur.fetchall()

        sensors = {}
        now = datetime.now(timezone.utc)

        for name, temp, ts in rows:
            try:
                sensor_time = ts

                if sensor_time.tzinfo is None:
                    sensor_time = sensor_time.replace(tzinfo=timezone.utc)

                sensors[name] = {
                    "temp": Decimal(str(temp)),
                    "age": (now - sensor_time).total_seconds(),
                }

            except Exception:
                logger.exception("Bad sensor row for %s", name)

        return sensors

    finally:
        if con:
            con.close()


def select_working_temperature(sensors):
    """Select best available fresh temperature source."""
    for sensor_name in SENSOR_PRIORITY:
        sensor = sensors.get(sensor_name)

        if not sensor:
            continue

        if sensor["age"] <= MAX_SENSOR_AGE_SECONDS:
            if sensor_name != "AverageInsideTemp":
                logger.warning("Using fallback sensor: %s", sensor_name)

            return sensor["temp"]

    logger.error("No valid fresh sensors available.")
    shutdownnow()


# ================================================================
# SCHEDULE / OVERRIDES
# ================================================================

def _coerce_time(value):
    """Handle MySQL TIME returned as datetime.time, timedelta, or string."""
    if hasattr(value, "hour"):
        return value

    if isinstance(value, timedelta):
        seconds = int(value.total_seconds()) % 86400
        return (datetime.min + timedelta(seconds=seconds)).time()

    return datetime.strptime(str(value), "%H:%M:%S").time()


@db_retry()
def get_schedule_settings():
    """Return the first active schedule row based on current time."""
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
            end_time = _coerce_time(row[7])

            if now_time < end_time:
                return {
                    "hightemp": Decimal(str(row[0])),
                    "lowtemp": Decimal(str(row[1])),
                    "hightemprange": Decimal(str(row[2])),
                    "lowtemprange": Decimal(str(row[3])),
                    "windowtemp": Decimal(str(row[4])),
                    "windowtemprange": Decimal(str(row[5])),
                    "circfan": int(row[6]),
                }

        raise RuntimeError("No valid schedule found.")

    finally:
        if con:
            con.close()


@db_retry()
def get_override_settings():
    """Return active window/fan override flags if unexpired."""
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

        window_expire = row[1]
        fan_expire = row[3]

        if window_expire.tzinfo is None:
            window_expire = window_expire.replace(tzinfo=timezone.utc)

        if fan_expire.tzinfo is None:
            fan_expire = fan_expire.replace(tzinfo=timezone.utc)

        return {
            "window": int(row[0]) == 1 and now < window_expire,
            "fan": int(row[2]) == 1 and now < fan_expire,
        }

    finally:
        if con:
            con.close()


@db_retry()
def get_window_state():
    """Read DB-backed window state. This prevents repeated open/close cycles."""
    con = None

    try:
        con = get_db_connection()

        with con.cursor() as cur:
            cur.execute("SELECT window FROM status WHERE id=1")
            row = cur.fetchone()

        return int(row[0])

    finally:
        if con:
            con.close()


# ================================================================
# CONTROL FUNCTIONS
# ================================================================

def heater_control(current_temp, low_temp, low_range):
    """Heater hysteresis with short-cycle protection."""
    effective_range = dynamic_hysteresis_range("heater", low_range)

    half = effective_range / 2
    lower = low_temp - half
    upper = low_temp + half

    if current_temp <= lower:
        if actuator_can_change("heater", True):
            GPIO.output(HEATER_GPIO, GPIO.HIGH)
            record_actuator_change("heater", True)
            update_status("UPDATE status SET heater=%s WHERE id=1", (1,))
            logger.info("Heater ON")

    elif current_temp >= upper:
        if actuator_can_change("heater", False):
            GPIO.output(HEATER_GPIO, GPIO.LOW)
            record_actuator_change("heater", False)
            update_status("UPDATE status SET heater=%s WHERE id=1", (0,))
            logger.info("Heater OFF")


def ventilation_control(current_temp, high_temp, high_range, override):
    """Ventilation fan hysteresis with override and short-cycle protection."""
    effective_range = dynamic_hysteresis_range("fan", high_range)

    half = effective_range / 2
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

    if not actuator_can_change("fan", fan_on):
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

    record_actuator_change("fan", fan_on)

    update_status(
        "UPDATE status SET fan=%s WHERE id=1",
        (1 if fan_on else 0,),
    )


def circulation_control(enabled):
    """Circulation fan follows schedule setting directly."""
    GPIO.output(CIRC_FAN_GPIO, GPIO.HIGH if enabled else GPIO.LOW)

    update_status(
        "UPDATE status SET circfan=%s WHERE id=1",
        (1 if enabled else 0,),
    )


def window_control(current_temp, target_temp, temp_range, override):
    """Window hysteresis with cooldown and reversal lockout."""
    effective_range = dynamic_hysteresis_range("window", temp_range)

    half = effective_range / 2
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
    logger.info("Greenhouse Controller v4.3 starting.")

    setup_gpio()

    update_status(
        """
        UPDATE status
        SET heater=0, fan=0, circfan=0, window=0
        WHERE id=1
        """,
        (),
    )

    time.sleep(5)

    try:
        while True:
            sensors = get_sensor_data()
            current_temp = select_working_temperature(sensors)

            settings = get_schedule_settings()
            overrides = get_override_settings()

            ventilation_control(
                current_temp,
                settings["hightemp"],
                settings["hightemprange"],
                overrides["fan"],
            )

            heater_control(
                current_temp,
                settings["lowtemp"],
                settings["lowtemprange"],
            )

            circulation_control(settings["circfan"])

            window_control(
                current_temp,
                settings["windowtemp"],
                settings["windowtemprange"],
                overrides["window"],
            )

            log_status_if_changed()

            time.sleep(20)

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received.")
        shutdownnow()

    except Exception:
        logger.exception("Fatal controller exception.")
        shutdownnow()


if __name__ == "__main__":
    main()
