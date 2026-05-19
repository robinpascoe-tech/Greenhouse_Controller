#!/usr/bin/env python3
#################################################################
# Green House Control Program                                   #
# Created by: Robin Pascoe      with code from several sources  #
#                                                               #
# Version 2026-05-18                                            #
# Refactored: 2026                                              #
#################################################################
"""
Greenhouse thermostat and environmental control system.
Controls:
- Heater
- Ventilation fans
- Circulation fan
- Roof and rear windows
Uses MySQL for configuration and status tracking.
Runs on Raspberry Pi GPIO.
"""
import sys
import time
import datetime
import configparser
import functools
import logging
import logging.handlers
from decimal import Decimal

import pymysql as mdb

# ── GPIO import with non-Pi fallback for development/testing ──────────────────
try:
    from RPi import GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
except ImportError:
    from unittest import mock
    GPIO = mock.MagicMock()
    print("WARNING: RPi.GPIO not available — running in mock mode.")

# ── Named sensor indices ───────────────────────────────────────────────────────
# These correspond to rows in the 'currenttemp' table (0-based after fetchall).
SENSOR_BACK  = 0
SENSOR_FRONT = 1
SENSOR_OUTSIDE = 2
SENSOR_AVG   = 4
SENSOR_WOODSTOVE = 5

# ── GPIO pin assignments ───────────────────────────────────────────────────────
WINDOW_REVERSER_GPIO = 22
WINDOW_GPIO          = 17
ROOF_REVERSER_GPIO   = 9
ROOF_GPIO            = 10
VENT_FAN_GPIO        = 5
AUX_VENT_FAN_GPIO    = 11
HEATER_GPIO          = 19
CIRC_FAN_GPIO        = 6
UNUSED_GPIO_1        = 13
UNUSED_GPIO_2        = 26
UNUSED_GPIO_3        = 27   # relay reportedly unreliable

# ── Status Logging state tracker ───────────────────────────────────────────────
last_status = {
    "heater": None,
    "fan": None,
    "circfan": None,
    "window": None
}
# ── Logging ────────────────────────────────────────────────────────────────────
LOG_FILENAME = '/home/pi/py3refactor/thermostat.log'
LOG_FORMAT   = "%(asctime)-15s %(levelname)-8s %(message)s"

my_logger = logging.getLogger("GreenhouseLogger")
my_logger.setLevel(logging.DEBUG)

fh = logging.handlers.RotatingFileHandler(
    LOG_FILENAME, maxBytes=5 * 1024 * 1024, backupCount=5
)
fh.setLevel(logging.DEBUG)
fh.setFormatter(logging.Formatter(LOG_FORMAT))
my_logger.addHandler(fh)

# Also log warnings and above to stderr so systemd/journalctl picks them up.
sh = logging.StreamHandler()
sh.setLevel(logging.WARNING)
sh.setFormatter(logging.Formatter(LOG_FORMAT))
my_logger.addHandler(sh)

# ── Database configuration ─────────────────────────────────────────────────────
# Credentials are read from /etc/greenhouse/greenhouse.conf so they are never
# stored in source code.  Example config file:
#
#   [database]
#   host     = localhost
#   user     = greenhouse
#   password = example_password
#   database = greenhouse
#
_db_config = configparser.ConfigParser()
_db_config.read('/home/pi/py3refactor/greenhouse.conf')

try:
    DB_HOST     = _db_config['database']['host']
    DB_USER     = _db_config['database']['user']
    DB_PASSWORD = _db_config['database']['password']
    DB_NAME     = _db_config['database']['database']
except KeyError:
    # Fall back to environment-variable-style defaults for backwards compatibility.
    # Remove this block once the config file is in place.
    my_logger.warning(
        "Could not read /etc/greenhouse/greenhouse.conf — "
        "falling back to hard-coded defaults.  "
        "Please create the config file."
    )
    DB_HOST     = 'localhost'
    DB_USER     = 'root'
    DB_PASSWORD = 'change_this_password'
    DB_NAME     = 'greenhouse'


# ─────────────────────────────────────────────────────────────────────────────
# Database helpers
# ─────────────────────────────────────────────────────────────────────────────

def db_retry(max_retries=5, delay=10):
    """Decorator: retry a function on MySQL errors before re-raising."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except mdb.Error as e:
                    last_exception = e
                    my_logger.warning(
                        "DB error in %s (attempt %d/%d): %s",
                        func.__name__, attempt, max_retries, e
                    )
                    time.sleep(delay)
            my_logger.error(
                "DB operation failed after %d retries in %s",
                max_retries, func.__name__
            )
            raise last_exception
        return wrapper
    return decorator


@db_retry()
def get_db_connection():
    """Open and return a MySQL connection."""
    return mdb.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        connect_timeout=5,
    )


@db_retry(max_retries=5, delay=10)
def update_status(query, values):
    """Execute an UPDATE against the status table."""
    con = None
    try:
        con = get_db_connection()
        cur = con.cursor()
        cur.execute(query, values)
        con.commit()
    except (mdb.Error, mdb.OperationalError, mdb.InterfaceError):
        if con:
            con.rollback()
        raise
    finally:
        if con:
            con.close()

@db_retry(max_retries=5, delay=10)
def log_status_if_changed():
    global last_status

    con = None
    try:
        con = get_db_connection()
        cur = con.cursor()

        cur.execute("SELECT heater, fan, circfan, window FROM status WHERE id = 1")
        row = cur.fetchone()

        if not row:
            return

        current = {
            "heater": int(row[0]),
            "fan": int(row[1]),
            "circfan": int(row[2]),
            "window": int(row[3]),
        }

        # check if anything changed
        if current == last_status:
            return  # no change → do not log

        # update cache
        last_status = current

        # insert event log
        cur.execute("""
            INSERT INTO status_log (heater, fan, circfan, window)
            VALUES (%s, %s, %s, %s)
        """, (
            current["heater"],
            current["fan"],
            current["circfan"],
            current["window"]
        ))

        con.commit()

    except mdb.Error as e:
        my_logger.error("Status change logging failed: %s", e)

    finally:
        if con:
            con.close()

# ─────────────────────────────────────────────────────────────────────────────
# GPIO setup & initial safe state
# ─────────────────────────────────────────────────────────────────────────────

def _setup_gpio():
    """Configure GPIO outputs and make sure everything starts in a safe state."""
    all_outputs = [
        WINDOW_REVERSER_GPIO, WINDOW_GPIO,
        ROOF_REVERSER_GPIO,   ROOF_GPIO,
        VENT_FAN_GPIO,        AUX_VENT_FAN_GPIO,
        HEATER_GPIO,          CIRC_FAN_GPIO,
        UNUSED_GPIO_1,        UNUSED_GPIO_2,
        UNUSED_GPIO_3,
    ]
    for pin in all_outputs:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)

    my_logger.debug("GPIO initialised; closing windows as safety measure.")

    # Close windows in case they were left open.
    GPIO.output(ROOF_REVERSER_GPIO,   GPIO.LOW)
    GPIO.output(WINDOW_REVERSER_GPIO, GPIO.LOW)
    GPIO.output(WINDOW_GPIO, GPIO.HIGH)
    time.sleep(20)
    GPIO.output(ROOF_GPIO, GPIO.HIGH)
    time.sleep(20)
    GPIO.output(ROOF_GPIO,   GPIO.LOW)
    GPIO.output(WINDOW_GPIO, GPIO.LOW)

    my_logger.debug("Windows Closed.")


# ─────────────────────────────────────────────────────────────────────────────
# Emergency shutdown
# ─────────────────────────────────────────────────────────────────────────────

def shutdownnow():
    """Put everything in a safe state and exit."""
    # Something's gone wrong, let's play it safe and shut everything down.
    my_logger.error("EMERGENCY SHUTDOWN triggered — closing all outputs.")
    print("EMERGENCY SHUTDOWN triggered — closing all outputs.")

    GPIO.output(VENT_FAN_GPIO,        GPIO.LOW)
    GPIO.output(AUX_VENT_FAN_GPIO,    GPIO.LOW)
    GPIO.output(CIRC_FAN_GPIO,        GPIO.LOW)
    GPIO.output(HEATER_GPIO,          GPIO.LOW)
    GPIO.output(UNUSED_GPIO_1,        GPIO.LOW)
    GPIO.output(UNUSED_GPIO_2,        GPIO.LOW)
    GPIO.output(UNUSED_GPIO_3,        GPIO.LOW)
    GPIO.output(ROOF_REVERSER_GPIO,   GPIO.LOW)
    GPIO.output(WINDOW_REVERSER_GPIO, GPIO.LOW)

    my_logger.error("EMERGENCY SHUTDOWN triggered — closing windows.")
    print("EMERGENCY SHUTDOWN triggered — CLOSING WINDOWS")

    GPIO.output(WINDOW_GPIO, GPIO.HIGH)
    time.sleep(20)
    GPIO.output(ROOF_GPIO, GPIO.HIGH)
    time.sleep(20)
    GPIO.output(ROOF_GPIO,   GPIO.LOW)
    GPIO.output(WINDOW_GPIO, GPIO.LOW)

    GPIO.cleanup()
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Database reads
# ─────────────────────────────────────────────────────────────────────────────

@db_retry(max_retries=5, delay=10)
def getmysqltemps():
    """
    Return (temperatures, tempages) from the currenttemp table.
    temperatures – list of Celsius strings.
    tempages     – list of float seconds since each reading was taken.
    """
    con = None
    try:
        con = get_db_connection()
        cur = con.cursor()
        cur.execute(
            "SELECT id, temperature, temperatureF, timestamp FROM currenttemp"
        )
        data = cur.fetchall()

        temperatures = []
        tempages     = []
        now = now = datetime.datetime.now(datetime.UTC)

        for row in data:
            temperatures.append(str(row[1]))
            row_time = datetime.datetime.fromisoformat(str(row[3]))
             # Assume DB timestamps are UTC if timezone info is missing
            if row_time.tzinfo is None:
                row_time = row_time.replace(tzinfo=datetime.UTC)
            tempages.append((now - row_time).total_seconds())

        return temperatures, tempages

    except mdb.Error as e:
        print("Error getting temperatures from DB: %s", e)
        my_logger.error("Error getting temperatures from DB: %s", e)
        raise
    finally:
        if con:
            con.close()


@db_retry(max_retries=5, delay=10)
def getschedulesettings():
    """
    Return the active schedule row as a tuple:
        (hightemp, lowtemp, hightemprange, lowtemprange,
         windowtemp, windowtemprange, circfan)

    Rows in the `settings` table are evaluated in order; the first one whose
    endtime is still in the future (relative to now) is used.
    """
    con = None
    try:
        con = get_db_connection()
        cur = con.cursor()
        cur.execute(
            "SELECT id, hightemp, lowtemp, hightemprange, lowtemprange, "
            "windowtemp, windowtemprange, starttime, endtime, circfan "
            "FROM settings"
        )
        rows = cur.fetchall()
    except mdb.Error as e:
        my_logger.error("Error getting schedule settings from DB: %s", e)
        raise
    finally:
        if con:
            con.close()

    now_time = datetime.datetime.strptime(
        time.strftime("%H:%M:%S"), "%H:%M:%S"
    ).time()

    for row in rows:
        end_time = datetime.datetime.strptime(str(row[8]), "%H:%M:%S").time()
        if now_time < end_time:
            # Return as strings to preserve existing Decimal conversion
            # in the control functions.
            return (
                str(row[1]),  # hightemp
                str(row[2]),  # lowtemp
                str(row[3]),  # hightemprange
                str(row[4]),  # lowtemprange
                str(row[5]),  # windowtemp
                str(row[6]),  # windowtemprange
                str(row[9]),  # circfan
            )
    
    my_logger.error("No valid schedule found for current time %s. Check the settings table end times.", now_time)
    raise RuntimeError(
        "No valid schedule found for current time {}. "
        "Check the settings table end times.".format(now_time)
    )


@db_retry(max_retries=5, delay=10)
def getoverridesettings():
    """
    Return (windowoverride, ventfanoverride) — each 1 if the override is
    active and unexpired, 0 otherwise.
    """
    con = None
    try:
        con = get_db_connection()
        cur = con.cursor()
        cur.execute(
            "SELECT id, windowoverride, windowexpire, fanoverride, fanexpire "
            "FROM overrides"
        )
        data = cur.fetchall()
    except mdb.Error as e:
        my_logger.error("Error getting override settings from DB: %s", e)
        raise
    finally:
        if con:
            con.close()

    now = now = datetime.datetime.now(datetime.UTC)
    row = data[0]

    window_override_active   = int(row[1]) == 1
    window_expire            = datetime.datetime.strptime(str(row[2]), "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.UTC)
    vent_fan_override_active = int(row[3]) == 1
    vent_fan_expire          = datetime.datetime.strptime(str(row[4]), "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.UTC)

    windowoverride  = 1 if (window_override_active   and now < window_expire)   else 0
    ventfanoverride = 1 if (vent_fan_override_active and now < vent_fan_expire) else 0

    return windowoverride, ventfanoverride


def _get_window_status():
    """Read current window state from the status table (0=closed, 1=open)."""
    con = None
    try:
        con = get_db_connection()
        cur = con.cursor()
        cur.execute("SELECT window FROM status WHERE id = %s", (1,))
        row = cur.fetchone()
        return int(row[0])
    except mdb.Error as e:
        my_logger.error("Error reading window status from DB: %s", e)
        raise
    finally:
        if con:
            con.close()


# ─────────────────────────────────────────────────────────────────────────────
# Control functions
# ─────────────────────────────────────────────────────────────────────────────

def ventilationfan(working_temp, high_temp, high_temp_range, ventfan_override):
    """
    Hysteresis control for ventilation fans.

    Fans turn ON  when temp rises above (high_temp + half_range).
    Fans turn OFF when temp falls below (high_temp - half_range).
    If ventfan_override == 1 the fans are forced on regardless of temperature.
    """
    half_range      = Decimal(high_temp_range) / 2
    working_temp    = Decimal(working_temp)
    high_temp       = Decimal(high_temp)
    lower_threshold = high_temp - half_range
    upper_threshold = high_temp + half_range

    if ventfan_override == 1:
        fan_on = True
    elif working_temp <= lower_threshold:
        fan_on = False
    elif working_temp >= upper_threshold:
        fan_on = True
    else:
        return  # Inside dead-band — leave fans as they are.

    if fan_on:
        GPIO.output(VENT_FAN_GPIO, GPIO.HIGH)
        time.sleep(1)
        GPIO.output(AUX_VENT_FAN_GPIO, GPIO.HIGH)
        my_logger.debug("Ventilation fans ON (temp=%.1f)", working_temp)
    else:
        GPIO.output(VENT_FAN_GPIO,     GPIO.LOW)
        GPIO.output(AUX_VENT_FAN_GPIO, GPIO.LOW)
        my_logger.debug("Ventilation fans OFF (temp=%.1f)", working_temp)

    try:
        update_status(
            "UPDATE status SET fan = %s WHERE id = %s",
            (1 if fan_on else 0, 1)
        )
    except mdb.Error as e:
        my_logger.error("Error updating fan status in DB: %s", e)


def heater(working_temp, low_temp, low_temp_range):
    """
    Hysteresis control for the heater.

    Heater turns ON  when temp falls below (low_temp - half_range).
    Heater turns OFF when temp rises above (low_temp + half_range).
    """
    half_range      = Decimal(low_temp_range) / 2
    working_temp    = Decimal(working_temp)
    low_temp        = Decimal(low_temp)
    lower_threshold = low_temp - half_range
    upper_threshold = low_temp + half_range

    if working_temp <= lower_threshold:
        heater_on = True
    elif working_temp >= upper_threshold:
        heater_on = False
    else:
        return  # Inside dead-band — leave heater as it is.

    if heater_on:
        GPIO.output(HEATER_GPIO, GPIO.HIGH)
        my_logger.debug("Heater ON (temp=%.1f)", working_temp)
    else:
        GPIO.output(HEATER_GPIO, GPIO.LOW)
        my_logger.debug("Heater OFF (temp=%.1f)", working_temp)

    try:
        update_status(
            "UPDATE status SET heater = %s WHERE id = %s",
            (1 if heater_on else 0, 1)
        )
    except mdb.Error as e:
        my_logger.error("Error updating heater status in DB: %s", e)


def circulationfan(circfan_setting):
    """Turn the circulation fan on (1) or off (0/anything else)."""
    fan_on = int(circfan_setting) == 1

    if fan_on:
        GPIO.output(CIRC_FAN_GPIO, GPIO.HIGH)
        my_logger.debug("Circulation fan ON")
    else:
        # Default safe state: off.
        GPIO.output(CIRC_FAN_GPIO, GPIO.LOW)
        my_logger.debug("Circulation fan OFF")

    try:
        update_status(
            "UPDATE status SET circfan = %s WHERE id = %s",
            (1 if fan_on else 0, 1)
        )
    except mdb.Error as e:
        my_logger.error("Error updating circulation fan status in DB: %s", e)


def window(working_temp, window_temp, window_temp_range, window_override):
    """
    Hysteresis control for roof and rear windows.

    Windows open  when temp rises above (window_temp + half_range).
    Windows close when temp falls below (window_temp - half_range).
    If window_override == 1 the windows are forced open.

    Window status is checked before acting to avoid double-opening or
    double-closing, which could damage the window mechanisms.
    """
    half_range      = Decimal(window_temp_range) / 2
    working_temp    = Decimal(working_temp)
    window_temp     = Decimal(window_temp)
    lower_threshold = window_temp - half_range
    upper_threshold = window_temp + half_range

    window_status = _get_window_status()

    if window_override == 1:
        should_open = True
    elif working_temp <= lower_threshold:
        should_open = False
    elif working_temp >= upper_threshold:
        should_open = True
    else:
        return  # Inside dead-band — leave windows as they are.

    if should_open and window_status == 0:
        _open_windows()
    elif not should_open and window_status == 1:
        _close_windows()


def _open_windows():
    """Physically open the rear window then the roof window."""
    my_logger.debug("Opening windows.")

    # Rear window first.
    GPIO.output(WINDOW_REVERSER_GPIO, GPIO.HIGH)
    time.sleep(0.5)
    GPIO.output(WINDOW_GPIO, GPIO.HIGH)
    time.sleep(35)
    GPIO.output(WINDOW_GPIO,          GPIO.LOW)
    GPIO.output(WINDOW_REVERSER_GPIO, GPIO.LOW)

    # Roof window.
    GPIO.output(ROOF_REVERSER_GPIO, GPIO.HIGH)
    time.sleep(0.5)
    GPIO.output(ROOF_GPIO, GPIO.HIGH)
    time.sleep(14)
    GPIO.output(ROOF_GPIO,          GPIO.LOW)
    GPIO.output(ROOF_REVERSER_GPIO, GPIO.LOW)

    try:
        update_status("UPDATE status SET window = %s WHERE id = %s", (1, 1))
    except mdb.Error as e:
        my_logger.error("Error updating window status to open in DB: %s", e)


def _close_windows():
    """Physically close the roof window then the rear window."""
    my_logger.debug("Closing windows.")

    GPIO.output(WINDOW_REVERSER_GPIO, GPIO.LOW)
    GPIO.output(ROOF_REVERSER_GPIO,   GPIO.LOW)
    time.sleep(0.5)

    GPIO.output(WINDOW_GPIO, GPIO.HIGH)
    time.sleep(24)
    GPIO.output(ROOF_GPIO, GPIO.HIGH)
    time.sleep(16)
    GPIO.output(WINDOW_GPIO, GPIO.LOW)
    GPIO.output(ROOF_GPIO,   GPIO.LOW)

    try:
        update_status("UPDATE status SET window = %s WHERE id = %s", (0, 1))
    except mdb.Error as e:
        my_logger.error("Error updating window status to closed in DB: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# Startup and main control loop
# ─────────────────────────────────────────────────────────────────────────────

def main():
    """Initialise the greenhouse and run the thermostat control loop."""
    my_logger.debug("Greenhouse Thermostat starting.")
    print("Greenhouse thermostat starting...")

    # Setup GPIO outputs.
    _setup_gpio()

    # Update Database to show that everything is OFF at startup, in case we crashed while something was on.
    try:
        update_status(
            "UPDATE status SET heater = %s, fan = %s, circfan = %s, window = %s "
            "WHERE id = %s",
            (0, 0, 0, 0, 1)
        )
    except mdb.Error as e:
        my_logger.error("Error updating database to show that everything is off: %s", e)

    # Let's wait another 5 seconds before we get underway.
    time.sleep(5)

    my_logger.debug("Entering main control loop.")

    try:
        while True:
            try:
                # Read temperatures in from database.
                temperatures, tempages = getmysqltemps()
                # Read override settings from database.
                win_override, fan_override = getoverridesettings()

                # Choose working temperature.
                # Prefer the front back average (SENSOR_AVG); fall back to the
                # front sensor if the average reading is stale (> 60s old).
                avg_age   = tempages[SENSOR_AVG]
                front_age = tempages[SENSOR_FRONT]

                if avg_age <= 60:
                    curr_temp = temperatures[SENSOR_AVG]
                elif front_age <= 60:
                    my_logger.warning(
                        "Average temp stale (%.0f s); falling back to front sensor.",
                        avg_age
                    )
                    curr_temp = temperatures[SENSOR_FRONT]
                else:
                    my_logger.error(
                        "All temperature readings are stale "
                        "(avg=%.0f s, front=%.0f s). Shutting down.",
                        avg_age, front_age
                    )
                    shutdownnow()
                    return  # shutdownnow() calls sys.exit(), but return makes
                            # it explicit to static analysers that curr_temp
                            # will never be used after this branch.

                # Read temperature settings from database.
                (
                    hi_temp,
                    lo_temp,
                    hi_temp_range,
                    lo_temp_range,
                    win_temp,
                    win_temp_range,
                    circfan,
                ) = getschedulesettings()

                ventilationfan(curr_temp, hi_temp, hi_temp_range, fan_override)
                heater(curr_temp, lo_temp, lo_temp_range)
                circulationfan(circfan)
                window(curr_temp, win_temp, win_temp_range, win_override)
                log_status_if_changed()

                time.sleep(20)

            except Exception as e:  # pylint: disable=broad-exception-caught
                my_logger.exception("Unexpected error in main loop: %s", e)
                shutdownnow()

    except KeyboardInterrupt:
        my_logger.debug("KeyboardInterrupt received — shutting down cleanly.")
        shutdownnow()
        print("Shutting down...")

    finally:
        GPIO.cleanup()


if __name__ == "__main__":
    main()
