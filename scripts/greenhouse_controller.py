#!/usr/bin/env python3
#################################################################
# Greenhouse Controller v4.3.2
#
# Direct drop-in replacement for the original controller with:
# - Original DB-driven schedule system
# - Original override system
# - Original GPIO mappings
# - Original status/status_log behavior
# - Name-keyed sensor handling
# - Sensor fallback policy
# - In-memory short-cycle protection
# - Window reversal lockout
# - Dynamic hysteresis widening
# - One-loop sensor freshness grace for delayed currenttemp updates
#
# v4.3.2 fixes:
# - Operator overrides bypass short-cycle protection
# - Override-triggered actuator changes still count toward cycle history
# - Startup DB reset failures are logged but do not prevent controller startup
#
# v4.3.1 fixes retained:
# - 24s + 16s close sequence is the standard close behavior everywhere
# - Forced startup/shutdown window closure does NOT start cooldown timer
# - Hardened DB datetime parsing
#################################################################

import sys
import time
import functools
import logging
import logging.handlers
import configparser
import signal
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from pathlib import Path

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
# Even unused relay outputs are intentionally forced LOW for safety.
UNUSED_GPIO_1 = 13
UNUSED_GPIO_2 = 26
UNUSED_GPIO_3 = 27


# ================================================================
# LOGGING
# ================================================================

LOG_FILENAME = "/home/pi/Greenhouse_Controller/thermostat.log"

logger = logging.getLogger("GreenhouseController")
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(asctime)s %(levelname)-8s %(message)s")

# Also log warnings/errors to stderr for journalctl/systemd visibility.
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.WARNING)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

try:
    Path(LOG_FILENAME).parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILENAME,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
except OSError as exc:
    # Logging should never prevent safe startup or test imports.
    logger.warning("File logging disabled: %s", exc)


# ================================================================
# DATABASE CONFIGURATION
# ================================================================

config = configparser.ConfigParser()
config.read("/home/pi/Greenhouse_Controller/greenhouse.conf")

try:
    DB_HOST = config["database"]["host"]
    DB_USER = config["database"]["user"]
    DB_PASSWORD = config["database"]["password"]
    DB_NAME = config["database"]["database"]
except Exception:
    logger.warning(
        "Could not load greenhouse.conf. Using placeholder DB fallback."
    )
    DB_HOST = "localhost"
    DB_USER = "greenhouse_app"
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

OUTSIDE_SENSOR_NAME = "OutsideTemp"
MAX_SENSOR_AGE_SECONDS = 90
MAX_RECENT_SENSOR_AGE_SECONDS = 120

# A single slightly late sensor-reader run should not stop the controller, but
# repeated stale readings still force the normal emergency shutdown path.
recent_sensor_grace_used = False

# Cooling strategy tuning. These conservative defaults only affect which
# cooling method is preferred once SQL thresholds already call for cooling.
COLD_OUTSIDE_TEMP = Decimal("5")
OUTSIDE_NEAR_INSIDE_DELTA = Decimal("3")


# ================================================================
# SHORT-CYCLE / ANTI-CHATTER CONFIGURATION
# ================================================================

ACTUATOR_RULES = {
    "heater": {
        "min_on": 300,          # stay on at least 5 min before off
        "min_off": 120,         # stay off at least 2 min before on
        "warn_cycles": 6,
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
# This avoids additional SQL schema complexity and is sufficient for this project.
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
# DATETIME HELPERS
# ================================================================

def parse_db_datetime(value):
    """
    Return a timezone-aware UTC datetime from common PyMySQL/MySQL values.

    MySQL/PyMySQL may return:
    - datetime.datetime
    - string like '2026-05-20 12:34:56'
    - string like '2026-05-20T12:34:56+00:00'

    The controller treats naive timestamps as UTC because read_sensors.py writes
    UTC timestamps and older MySQL DATETIME columns may not preserve timezone.
    """

    if value is None:
        raise ValueError("Cannot parse None as datetime")

    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).strip())

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def coerce_time(value):
    """
    Handle MySQL TIME returned as datetime.time, timedelta, or string.
    """

    if hasattr(value, "hour"):
        return value

    if isinstance(value, timedelta):
        seconds = int(value.total_seconds()) % 86400
        return (datetime.min + timedelta(seconds=seconds)).time()

    return datetime.strptime(str(value), "%H:%M:%S").time()


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
def ensure_singleton_rows():
    """Repair required one-row runtime tables if a row was deleted."""

    con = None
    try:
        con = get_db_connection()
        with con.cursor() as cur:
            cur.execute(
                """
                INSERT INTO status
                (id, heater, fan, circfan, window)
                VALUES (1, 0, 0, 0, 0)
                ON DUPLICATE KEY UPDATE id=VALUES(id)
                """
            )
            cur.execute(
                """
                INSERT INTO overrides
                (id, windowoverride, windowexpire, fanoverride, fanexpire)
                VALUES
                (1, 0, '2010-01-01 00:00:00', 0, '2010-01-01 00:00:00')
                ON DUPLICATE KEY UPDATE id=VALUES(id)
                """
            )
        con.commit()
    except Exception:
        if con:
            con.rollback()
        raise
    finally:
        if con:
            con.close()


@db_retry()
def log_status_if_changed():
    """
    Preserve original status_log behavior:
    only insert rows when actuator state changes.
    """

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

def prune_cycle_history(actuator):
    """Keep only recent actuator transitions for cycle-rate detection."""
    now = time.monotonic()
    ACTUATOR_STATE[actuator]["changes"] = [
        t for t in ACTUATOR_STATE[actuator]["changes"]
        if now - t <= CYCLE_HISTORY_SECONDS
    ]


def record_actuator_change(actuator, new_state):
    """
    Record actuator transition for short-cycle and dynamic hysteresis logic.

    Forced startup/shutdown window moves intentionally bypass this so they do
    not poison the normal operating cooldown timer.

    Operator overrides DO record because they are real operational actuator
    movements and should count toward cycle history.
    """

    now = time.monotonic()

    ACTUATOR_STATE[actuator]["state"] = new_state
    ACTUATOR_STATE[actuator]["last_change"] = now
    ACTUATOR_STATE[actuator]["changes"].append(now)

    prune_cycle_history(actuator)


def actuator_can_change(actuator, desired_state):
    """
    Enforce minimum ON/OFF durations.

    Emergency shutdown, forced startup close, and operator overrides may bypass
    this function by design.
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

    prune_cycle_history(actuator)

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

    This protects relays, motors, and gear mechanisms.

    Operator window override bypasses this by design because it represents a
    deliberate manual command.
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
    """
    Initialize all GPIO outputs to safe LOW state.

    The forced startup close updates DB window state but does not record an
    actuator cycle, so the controller can still open windows immediately after
    startup if temperature or override requires it.
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
        UNUSED_GPIO_3,
    ]

    for pin in outputs:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)

    logger.info("GPIO initialized to safe LOW state.")

    # Original safety behavior retained: close windows at startup.
    # record=False avoids starting the normal window cooldown timer.
    close_windows(force=True, record=False)


# ================================================================
# WINDOW CONTROL
# ================================================================

def open_windows(force=False, record=True):
    """
    Open rear window then roof window.

    Original timing preserved:
    - rear window: 35s
    - roof window: 14s

    force=True bypasses short-cycle/reversal protection.
    record=True still records the actuator move for cycle analysis.
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

    ACTUATOR_STATE["window"]["state"] = True
    ACTUATOR_STATE["window"]["last_direction"] = "open"

    if record:
        record_actuator_change("window", True)

    update_window_status(1)


def close_windows(force=False, record=True):
    """
    Close windows using the standard close sequence.

    v4.3.2 design decision:
    - 24s + 16s is the standard close sequence everywhere:
      normal close, startup close, and emergency shutdown close.
    - Forced startup/shutdown closes may update DB state without recording
      an anti-cycle transition.
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

    ACTUATOR_STATE["window"]["state"] = False
    ACTUATOR_STATE["window"]["last_direction"] = "close"

    if record:
        record_actuator_change("window", False)

    update_window_status(0)


# ================================================================
# EMERGENCY SHUTDOWN
# ================================================================

def shutdownnow():
    """
    Emergency safe shutdown.

    Design decision:
    - Short-cycle protection is bypassed.
    - Standard close timing is used: 24s + 16s.
    - record=False avoids contaminating normal operating cycle history.
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

        close_windows(force=True, record=False)

    except Exception:
        logger.exception("Error during emergency shutdown.")

    finally:
        GPIO.cleanup()

    sys.exit(1)


def handle_shutdown_signal(signum, _frame):
    """Route systemd/service stop signals through the safe shutdown path."""
    logger.warning("Signal %s received; shutting down safely.", signum)
    shutdownnow()


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
                sensor_time = parse_db_datetime(ts)

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

    global recent_sensor_grace_used

    for sensor_name in SENSOR_PRIORITY:
        sensor = sensors.get(sensor_name)

        if not sensor:
            continue

        if sensor["age"] <= MAX_SENSOR_AGE_SECONDS:
            recent_sensor_grace_used = False

            if sensor_name != "AverageInsideTemp":
                logger.warning("Using fallback sensor: %s", sensor_name)

            return sensor["temp"]

    # Allow one controller loop to ride through a slightly delayed sensor update.
    # This protects against a missed cron edge while preserving fail-safe behavior
    # if read_sensors.py truly stops updating currenttemp.
    if not recent_sensor_grace_used:
        for sensor_name in SENSOR_PRIORITY:
            sensor = sensors.get(sensor_name)

            if not sensor:
                continue

            if sensor["age"] <= MAX_RECENT_SENSOR_AGE_SECONDS:
                recent_sensor_grace_used = True
                logger.warning(
                    "Using recent but stale sensor %s at %.0fs old.",
                    sensor_name,
                    sensor["age"],
                )
                return sensor["temp"]

    logger.error("No valid fresh sensors available.")
    shutdownnow()


def select_outside_temperature(sensors):
    """
    Return fresh outside temperature if available.

    Outside temperature improves cooling decisions, but it is not a safety
    prerequisite. If the outside sensor is missing or stale, the controller
    falls back to the original inside-temperature-only behavior.
    """

    sensor = sensors.get(OUTSIDE_SENSOR_NAME)

    if not sensor:
        logger.debug("Outside temperature unavailable; using legacy cooling.")
        return None

    if sensor["age"] > MAX_SENSOR_AGE_SECONDS:
        logger.warning(
            "Outside temperature is stale (%.0fs old); using legacy cooling.",
            sensor["age"],
        )
        return None

    return sensor["temp"]


# ================================================================
# SCHEDULE / OVERRIDES
# ================================================================

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
                ORDER BY endtime
                """
            )
            rows = cur.fetchall()

        now_time = datetime.now().time()

        for row in rows:
            end_time = coerce_time(row[7])

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

        if rows:
            logger.warning(
                "No schedule endtime is after current time %s; using final row.",
                now_time,
            )
            row = rows[-1]
            return {
                "hightemp": Decimal(str(row[0])),
                "lowtemp": Decimal(str(row[1])),
                "hightemprange": Decimal(str(row[2])),
                "lowtemprange": Decimal(str(row[3])),
                "windowtemp": Decimal(str(row[4])),
                "windowtemprange": Decimal(str(row[5])),
                "circfan": int(row[6]),
            }

        raise RuntimeError("No schedule rows found.")

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
                WHERE id=1
                """
            )
            row = cur.fetchone()

        if not row:
            logger.warning("No overrides row found; assuming no active overrides.")
            return {
                "window": False,
                "fan": False,
            }

        now = datetime.now(timezone.utc)

        window_expire = parse_db_datetime(row[1])
        fan_expire = parse_db_datetime(row[3])

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

        if not row:
            logger.warning("No status row found; assuming windows closed.")
            return 0

        return int(row[0])

    finally:
        if con:
            con.close()


# ================================================================
# CONTROL FUNCTIONS
# ================================================================

@dataclass(frozen=True)
class ActuatorDecision:
    """
    Desired actuator state from pure control decision logic.

    state:
        True means ON/open, False means OFF/closed, None means hold current
        state.
    bypass_protection:
        True when an operator override should bypass short-cycle or reversal
        protection while still recording the actuator movement.
    reason:
        Short label useful for logging and future simulation assertions.
    """

    state: bool | None
    bypass_protection: bool = False
    reason: str = "hold"


@dataclass(frozen=True)
class CoolingDecision:
    """
    Paired fan/window decision from greenhouse-aware cooling strategy.

    Keeping the pair together lets the controller prefer one cooling method
    without losing the existing per-actuator safety checks.
    """

    fan: ActuatorDecision
    window: ActuatorDecision
    strategy: str = "legacy"


def hysteresis_bounds(target_temp, temp_range):
    """Return lower and upper thresholds around a target temperature."""

    half = Decimal(temp_range) / 2
    return Decimal(target_temp) - half, Decimal(target_temp) + half


def decide_heater_state(current_temp, low_temp, effective_range):
    """Return heater decision from low-temperature hysteresis only."""

    lower, upper = hysteresis_bounds(low_temp, effective_range)

    if current_temp <= lower:
        return ActuatorDecision(True, reason="below_low_threshold")

    if current_temp >= upper:
        return ActuatorDecision(False, reason="above_low_threshold")

    return ActuatorDecision(None)


def decide_fan_state(current_temp, high_temp, effective_range, override):
    """Return ventilation fan decision from override and high-temperature hysteresis."""

    if override:
        return ActuatorDecision(True, bypass_protection=True, reason="override")

    lower, upper = hysteresis_bounds(high_temp, effective_range)

    if current_temp >= upper:
        return ActuatorDecision(True, reason="above_high_threshold")

    if current_temp <= lower:
        return ActuatorDecision(False, reason="below_high_threshold")

    return ActuatorDecision(None)


def decide_window_state(current_temp, target_temp, effective_range, override):
    """Return window decision from override and window-temperature hysteresis."""

    if override:
        return ActuatorDecision(True, bypass_protection=True, reason="override")

    lower, upper = hysteresis_bounds(target_temp, effective_range)

    if current_temp >= upper:
        return ActuatorDecision(True, reason="above_window_threshold")

    if current_temp <= lower:
        return ActuatorDecision(False, reason="below_window_threshold")

    return ActuatorDecision(None)


def decide_cooling_strategy(
    current_temp,
    outside_temp,
    high_temp,
    high_range,
    window_temp,
    window_range,
    fan_override,
    window_override,
):
    """
    Choose coordinated fan/window cooling behavior.

    The strategy preserves manual overrides and falls back to the original
    independent fan/window hysteresis when outside temperature is unavailable.
    Adaptive behavior only changes opening/cooling choices once the configured
    thresholds already call for cooling.
    """

    current_temp = Decimal(current_temp)
    high_temp = Decimal(high_temp)
    high_range = Decimal(high_range)
    window_temp = Decimal(window_temp)
    window_range = Decimal(window_range)

    fan = decide_fan_state(current_temp, high_temp, high_range, fan_override)
    window = decide_window_state(
        current_temp,
        window_temp,
        window_range,
        window_override,
    )

    if fan_override or window_override:
        return CoolingDecision(fan, window, "override")

    if outside_temp is None:
        return CoolingDecision(fan, window, "legacy_no_outside_temp")

    outside_temp = Decimal(outside_temp)
    fan_lower, fan_upper = hysteresis_bounds(high_temp, high_range)
    window_lower, _window_upper = hysteresis_bounds(window_temp, window_range)
    urgent_temp = max(high_temp + high_range, window_temp + window_range)

    if current_temp >= urgent_temp:
        return CoolingDecision(
            ActuatorDecision(True, reason="urgent_cooling"),
            ActuatorDecision(True, reason="urgent_cooling"),
            "urgent_cooling",
        )

    if current_temp <= min(fan_lower, window_lower):
        return CoolingDecision(fan, window, "cooling_not_needed")

    cooling_requested = fan.state is True or window.state is True

    if not cooling_requested:
        return CoolingDecision(fan, window, "within_hysteresis")

    outside_delta = current_temp - outside_temp

    if outside_temp <= COLD_OUTSIDE_TEMP:
        return CoolingDecision(
            ActuatorDecision(True, reason="cold_outside_fan_preferred"),
            ActuatorDecision(False, reason="cold_outside_window_avoided"),
            "cold_outside_fan_preferred",
        )

    if outside_delta < 0:
        return CoolingDecision(
            (
                ActuatorDecision(True, reason="outside_warmer_fan_threshold")
                if current_temp >= fan_upper
                else fan
            ),
            ActuatorDecision(False, reason="outside_warmer_window_avoided"),
            "outside_warmer_window_avoided",
        )

    if outside_delta <= OUTSIDE_NEAR_INSIDE_DELTA:
        return CoolingDecision(
            ActuatorDecision(False, reason="near_outside_window_preferred"),
            ActuatorDecision(True, reason="near_outside_window_preferred"),
            "near_outside_window_preferred",
        )

    return CoolingDecision(
        ActuatorDecision(False, reason="cool_outside_window_preferred"),
        ActuatorDecision(True, reason="cool_outside_window_preferred"),
        "cool_outside_window_preferred",
    )


def heater_control(current_temp, low_temp, low_range):
    """Heater hysteresis with short-cycle protection."""

    effective_range = dynamic_hysteresis_range("heater", low_range)
    decision = decide_heater_state(current_temp, low_temp, effective_range)

    if decision.state is True:
        if actuator_can_change("heater", decision.state):
            GPIO.output(HEATER_GPIO, GPIO.HIGH)
            record_actuator_change("heater", decision.state)
            update_status("UPDATE status SET heater=%s WHERE id=1", (1,))
            logger.info("Heater ON")

    elif decision.state is False:
        if actuator_can_change("heater", decision.state):
            GPIO.output(HEATER_GPIO, GPIO.LOW)
            record_actuator_change("heater", decision.state)
            update_status("UPDATE status SET heater=%s WHERE id=1", (0,))
            logger.info("Heater OFF")


def apply_fan_decision(decision):
    """Apply a fan decision through GPIO, SQL, and short-cycle protection."""

    if decision.state is None:
        return

    current_state = ACTUATOR_STATE["fan"]["state"]

    if current_state == decision.state:
        return

    if not decision.bypass_protection and not actuator_can_change(
        "fan",
        decision.state,
    ):
        return

    if decision.state:
        GPIO.output(VENT_FAN_GPIO, GPIO.HIGH)
        time.sleep(1)
        GPIO.output(AUX_VENT_FAN_GPIO, GPIO.HIGH)
        logger.info("Ventilation fans ON")
    else:
        GPIO.output(VENT_FAN_GPIO, GPIO.LOW)
        GPIO.output(AUX_VENT_FAN_GPIO, GPIO.LOW)
        logger.info("Ventilation fans OFF")

    record_actuator_change("fan", decision.state)

    update_status(
        "UPDATE status SET fan=%s WHERE id=1",
        (1 if decision.state else 0,),
    )


def ventilation_control(current_temp, high_temp, high_range, override):
    """
    Ventilation fan hysteresis with override and short-cycle protection.

    Operator override intentionally bypasses short-cycle protection but still
    records the actuator transition.
    """

    effective_range = dynamic_hysteresis_range("fan", high_range)
    decision = decide_fan_state(
        current_temp,
        high_temp,
        effective_range,
        override,
    )
    apply_fan_decision(decision)


def circulation_control(enabled):
    """Circulation fan follows schedule setting directly."""

    GPIO.output(CIRC_FAN_GPIO, GPIO.HIGH if enabled else GPIO.LOW)

    update_status(
        "UPDATE status SET circfan=%s WHERE id=1",
        (1 if enabled else 0,),
    )


def apply_window_decision(decision):
    """Apply a window decision through motor sequencing and SQL state."""

    if decision.state is None:
        return

    current_state = get_window_state()

    if decision.state and current_state == 0:
        open_windows(force=decision.bypass_protection, record=True)

    elif not decision.state and current_state == 1:
        close_windows(force=decision.bypass_protection, record=True)


def window_control(current_temp, target_temp, temp_range, override):
    """
    Window hysteresis with cooldown and reversal lockout.

    Operator override intentionally bypasses window short-cycle and reversal
    protection but still records the movement.
    """

    effective_range = dynamic_hysteresis_range("window", temp_range)
    decision = decide_window_state(
        current_temp,
        target_temp,
        effective_range,
        override,
    )
    apply_window_decision(decision)


def get_cooling_decision(current_temp, outside_temp, settings, overrides):
    """Return coordinated fan/window cooling decision for the current state."""

    fan_range = dynamic_hysteresis_range("fan", settings["hightemprange"])
    window_range = dynamic_hysteresis_range("window", settings["windowtemprange"])

    return decide_cooling_strategy(
        current_temp,
        outside_temp,
        settings["hightemp"],
        fan_range,
        settings["windowtemp"],
        window_range,
        overrides["fan"],
        overrides["window"],
    )


def cooling_control(current_temp, outside_temp, settings, overrides):
    """
    Coordinate fan and window cooling using outside temperature when available.

    This is the first adaptive layer: it chooses which cooling path to prefer,
    then existing actuator protections still decide whether movement is allowed.
    """

    decision = get_cooling_decision(
        current_temp,
        outside_temp,
        settings,
        overrides,
    )

    logger.debug("Cooling strategy selected: %s", decision.strategy)
    apply_fan_decision(decision.fan)
    apply_window_decision(decision.window)


# ================================================================
# MAIN LOOP
# ================================================================

def main():
    logger.info("Greenhouse Controller v4.3.2 starting.")

    signal.signal(signal.SIGTERM, handle_shutdown_signal)

    setup_gpio()

    # Preserve original startup DB reset behavior, but do not let DB reset
    # failure prevent the controller from starting.
    try:
        ensure_singleton_rows()
        update_status(
            """
            UPDATE status
            SET heater=0, fan=0, circfan=0, window=0
            WHERE id=1
            """,
            (),
        )
    except Exception:
        logger.exception("Startup status reset failed; continuing controller startup.")

    time.sleep(5)

    try:
        while True:
            sensors = get_sensor_data()
            current_temp = select_working_temperature(sensors)
            outside_temp = select_outside_temperature(sensors)

            settings = get_schedule_settings()
            overrides = get_override_settings()

            cooling_decision = get_cooling_decision(
                current_temp,
                outside_temp,
                settings,
                overrides,
            )
            logger.debug(
                "Cooling strategy selected: %s",
                cooling_decision.strategy,
            )

            apply_fan_decision(cooling_decision.fan)

            heater_control(
                current_temp,
                settings["lowtemp"],
                settings["lowtemprange"],
            )

            circulation_control(settings["circfan"])

            apply_window_decision(cooling_decision.window)

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
