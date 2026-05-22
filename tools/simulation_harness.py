#!/usr/bin/env python3
"""
Temporary Raspberry Pi simulation harness for greenhouse controller testing.

Runs against a throwaway MariaDB database and monkeypatches GPIO/time so no
real relays move and long window timings complete instantly.
"""

from __future__ import annotations

import importlib
import math
import os
import signal
import sys
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path

import pymysql


# The harness needs admin SQL permissions because it creates and drops a
# throwaway database. Keep this out of source control by exporting:
#   GREENHOUSE_TEST_DB_ROOT_PASSWORD='your-root-password'
ROOT_PASSWORD = os.environ.get("GREENHOUSE_TEST_DB_ROOT_PASSWORD", "")
TEST_DB = "greenhouse_controller_sim_test"
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
SQL_DIR = PROJECT_ROOT / "sql"


class FakeClock:
    """Fake monotonic clock so multi-minute relay delays complete instantly."""

    def __init__(self, start=10_000.0):
        self.t = float(start)

    def monotonic(self):
        return self.t

    def sleep(self, seconds):
        self.t += float(seconds)

    def advance(self, seconds):
        self.t += float(seconds)


class GPIORecorder:
    """Minimal RPi.GPIO stand-in that records pin writes instead of moving relays."""

    BCM = "BCM"
    OUT = "OUT"
    HIGH = 1
    LOW = 0

    def __init__(self, clock):
        self.clock = clock
        self.events = []
        self.pin_state = {}
        self.cleanup_called = False

    def setmode(self, mode):
        self.events.append((self.clock.monotonic(), "setmode", mode))

    def setwarnings(self, enabled):
        self.events.append((self.clock.monotonic(), "setwarnings", enabled))

    def setup(self, pin, mode):
        self.events.append((self.clock.monotonic(), "setup", pin, mode))

    def output(self, pin, state):
        self.pin_state[pin] = state
        self.events.append((self.clock.monotonic(), "output", pin, state))

    def cleanup(self):
        self.cleanup_called = True
        self.events.append((self.clock.monotonic(), "cleanup"))


def root_conn(db=None, autocommit=True):
    """Open a MariaDB root connection for throwaway test database setup."""
    if not ROOT_PASSWORD:
        raise RuntimeError(
            "Set GREENHOUSE_TEST_DB_ROOT_PASSWORD before running the simulation harness."
        )

    return pymysql.connect(
        host="localhost",
        user="root",
        password=ROOT_PASSWORD,
        database=db,
        autocommit=autocommit,
    )


def execute_schema():
    """Create a fresh throwaway database from sql/schema.sql."""
    schema = (SQL_DIR / "schema.sql").read_text()
    schema = schema.replace("`greenhouse`", f"`{TEST_DB}`")

    statements = []
    current = []
    for line in schema.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        current.append(line)
        if stripped.endswith(";"):
            stmt = "\n".join(current).rstrip(";")
            current = []
            upper = stmt.upper()
            if upper.startswith(("SET ", "START TRANSACTION", "COMMIT")):
                continue
            if upper.startswith(("CREATE USER", "GRANT ", "FLUSH PRIVILEGES")):
                continue
            statements.append(stmt)

    con = root_conn()
    try:
        with con.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS `{TEST_DB}`")
            for stmt in statements:
                cur.execute(stmt)
    finally:
        con.close()

    copy_live_settings()


def copy_live_settings():
    """Copy live schedule values so simulations use realistic thresholds."""
    con = root_conn(autocommit=False)
    try:
        with con.cursor() as cur:
            cur.execute(
                """
                SELECT id, hightemp, lowtemp, hightemprange, lowtemprange,
                       windowtemp, windowtemprange, starttime, endtime, circfan
                FROM greenhouse.settings
                ORDER BY id
                """
            )
            rows = cur.fetchall()

            cur.execute(f"DELETE FROM `{TEST_DB}`.settings")
            cur.executemany(
                f"""
                INSERT INTO `{TEST_DB}`.settings
                (id, hightemp, lowtemp, hightemprange, lowtemprange,
                 windowtemp, windowtemprange, starttime, endtime, circfan)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                rows,
            )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def patch_modules():
    """Import runtime modules and point them at the throwaway database."""
    sys.path.insert(0, str(SCRIPTS_DIR))

    thermostat = importlib.import_module("greenhouse_controller")
    sensor_health = importlib.import_module("sensor_health")
    read_sensors = importlib.import_module("read_sensors")

    for mod in (thermostat, sensor_health, read_sensors):
        mod.DB_HOST = "localhost"
        mod.DB_USER = "root"
        mod.DB_PASSWORD = ROOT_PASSWORD
        mod.DB_NAME = TEST_DB

    clock = FakeClock()
    gpio = GPIORecorder(clock)
    thermostat.GPIO = gpio
    thermostat.time.monotonic = clock.monotonic
    thermostat.time.sleep = clock.sleep

    return thermostat, sensor_health, read_sensors, clock, gpio


def reset_controller_state(thermostat, clock, gpio):
    """Reset in-memory actuator state and singleton DB rows between tests."""
    clock.t = 10_000.0
    gpio.events.clear()
    gpio.pin_state.clear()
    gpio.cleanup_called = False

    for name, state in thermostat.ACTUATOR_STATE.items():
        state["state"] = False
        state["last_change"] = 0.0
        state["changes"] = []
        if name == "window":
            state["last_direction"] = None

    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            cur.execute(
                "UPDATE status SET heater=0, fan=0, circfan=0, window=0 WHERE id=1"
            )
            cur.execute(
                """
                UPDATE overrides
                SET windowoverride=0,
                    windowexpire='2010-01-01 00:00:00',
                    fanoverride=0,
                    fanexpire='2010-01-01 00:00:00'
                WHERE id=1
                """
            )
    finally:
        con.close()


def scalar(sql):
    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            cur.execute(sql)
            return cur.fetchone()[0]
    finally:
        con.close()


def count_gpio_outputs(thermostat, pins):
    return sum(
        1
        for event in thermostat.GPIO.events
        if len(event) >= 4 and event[1] == "output" and event[2] in pins
    )


def status_row():
    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            cur.execute("SELECT heater, fan, circfan, window FROM status WHERE id=1")
            return cur.fetchone()
    finally:
        con.close()


def seed_currenttemp_rows():
    now = datetime.now(timezone.utc)
    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            rows = (
                (1, "BackTemp"),
                (2, "FrontTemp"),
                (3, "OutsideTemp"),
                (4, "PiTemp"),
                (5, "AverageInsideTemp"),
                (6, "WoodstoveTemp"),
            )
            for row_id, name in rows:
                cur.execute(
                    """
                    INSERT INTO currenttemp
                    (id, temperature, temperatureF, timestamp, Name)
                    VALUES (%s, 20.00, 68.00, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        temperature=VALUES(temperature),
                        temperatureF=VALUES(temperatureF),
                        timestamp=VALUES(timestamp),
                        Name=VALUES(Name)
                    """,
                    (row_id, now, name),
                )
    finally:
        con.close()


def clear_sensor_health_tables():
    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            for table in (
                "sensor_alerts",
                "sensor_health",
                "sensor_state",
                "sensor_diagnostics",
                "sensor_profile",
            ):
                cur.execute(f"DELETE FROM {table}")
    finally:
        con.close()


def simulated_schedule_settings(sim_seconds):
    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            cur.execute(
                """
                SELECT hightemp, lowtemp, hightemprange, lowtemprange,
                       windowtemp, windowtemprange, circfan, endtime
                FROM settings
                ORDER BY endtime
                """
            )
            rows = cur.fetchall()
    finally:
        con.close()

    for row in rows:
        end_seconds = int(row[7].total_seconds())
        if sim_seconds < end_seconds:
            selected = row
            break
    else:
        selected = rows[-1]

    return {
        "hightemp": Decimal(str(selected[0])),
        "lowtemp": Decimal(str(selected[1])),
        "hightemprange": Decimal(str(selected[2])),
        "lowtemprange": Decimal(str(selected[3])),
        "windowtemp": Decimal(str(selected[4])),
        "windowtemprange": Decimal(str(selected[5])),
        "circfan": int(selected[6]),
    }


def update_currenttemps(inside, outside):
    now = datetime.now(timezone.utc)
    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            for name, value in (
                ("FrontTemp", inside),
                ("BackTemp", inside),
                ("AverageInsideTemp", inside),
                ("OutsideTemp", outside),
            ):
                cur.execute(
                    """
                    UPDATE currenttemp
                    SET temperature=%s,
                        temperatureF=%s,
                        timestamp=%s
                    WHERE Name=%s
                    """,
                    (
                        value,
                        (value * Decimal("9") / Decimal("5")) + Decimal("32"),
                        now,
                        name,
                    ),
                )
    finally:
        con.close()


def simulate_heater(thermostat, clock):
    reset_controller_state(thermostat, clock, thermostat.GPIO)
    temps = [Decimal("8.7"), Decimal("11.3")] * 12
    max_range = Decimal("0")
    for temp in temps:
        thermostat.heater_control(temp, Decimal("10"), Decimal("2"))
        max_range = max(
            max_range,
            thermostat.dynamic_hysteresis_range("heater", Decimal("2")),
        )
        clock.advance(310)
    return {
        "changes": len(thermostat.ACTUATOR_STATE["heater"]["changes"]),
        "possible_changes_without_widening": len(temps),
        "max_effective_range": str(max_range),
        "final_state": thermostat.ACTUATOR_STATE["heater"]["state"],
    }


def test_decision_helpers(thermostat):
    """Verify pure actuator decisions before GPIO/SQL side effects are applied."""
    cases = {
        "heater_on": thermostat.decide_heater_state(
            Decimal("8.9"),
            Decimal("10"),
            Decimal("2"),
        ),
        "heater_hold": thermostat.decide_heater_state(
            Decimal("10.0"),
            Decimal("10"),
            Decimal("2"),
        ),
        "heater_off": thermostat.decide_heater_state(
            Decimal("11.1"),
            Decimal("10"),
            Decimal("2"),
        ),
        "fan_on": thermostat.decide_fan_state(
            Decimal("26.1"),
            Decimal("25"),
            Decimal("2"),
            False,
        ),
        "fan_hold": thermostat.decide_fan_state(
            Decimal("25.0"),
            Decimal("25"),
            Decimal("2"),
            False,
        ),
        "fan_off": thermostat.decide_fan_state(
            Decimal("23.9"),
            Decimal("25"),
            Decimal("2"),
            False,
        ),
        "fan_override": thermostat.decide_fan_state(
            Decimal("10"),
            Decimal("25"),
            Decimal("2"),
            True,
        ),
        "window_open": thermostat.decide_window_state(
            Decimal("31.1"),
            Decimal("30"),
            Decimal("2"),
            False,
        ),
        "window_hold": thermostat.decide_window_state(
            Decimal("30.0"),
            Decimal("30"),
            Decimal("2"),
            False,
        ),
        "window_close": thermostat.decide_window_state(
            Decimal("28.9"),
            Decimal("30"),
            Decimal("2"),
            False,
        ),
        "window_override": thermostat.decide_window_state(
            Decimal("10"),
            Decimal("30"),
            Decimal("2"),
            True,
        ),
    }

    return {
        name: {
            "state": decision.state,
            "bypass_protection": decision.bypass_protection,
            "reason": decision.reason,
        }
        for name, decision in cases.items()
    }


def describe_cooling_decision(decision):
    return {
        "strategy": decision.strategy,
        "fan": {
            "state": decision.fan.state,
            "bypass_protection": decision.fan.bypass_protection,
            "reason": decision.fan.reason,
        },
        "window": {
            "state": decision.window.state,
            "bypass_protection": decision.window.bypass_protection,
            "reason": decision.window.reason,
        },
    }


def test_outside_aware_cooling_strategy(thermostat):
    """Exercise coordinated fan/window decisions across outside conditions."""

    high = Decimal("36")
    high_range = Decimal("4")
    window = Decimal("33")
    window_range = Decimal("6")

    cases = {
        "legacy_without_outside": thermostat.decide_cooling_strategy(
            Decimal("37"),
            None,
            high,
            high_range,
            window,
            window_range,
            False,
            False,
        ),
        "cold_outside_prefers_fans": thermostat.decide_cooling_strategy(
            Decimal("37"),
            Decimal("-5"),
            high,
            high_range,
            window,
            window_range,
            False,
            False,
        ),
        "near_outside_prefers_windows": thermostat.decide_cooling_strategy(
            Decimal("37"),
            Decimal("35"),
            high,
            high_range,
            window,
            window_range,
            False,
            False,
        ),
        "cool_outside_prefers_windows": thermostat.decide_cooling_strategy(
            Decimal("37"),
            Decimal("20"),
            high,
            high_range,
            window,
            window_range,
            False,
            False,
        ),
        "warmer_outside_avoids_windows": thermostat.decide_cooling_strategy(
            Decimal("37"),
            Decimal("39"),
            high,
            high_range,
            window,
            window_range,
            False,
            False,
        ),
        "urgent_cooling_uses_both": thermostat.decide_cooling_strategy(
            Decimal("41"),
            Decimal("-5"),
            high,
            high_range,
            window,
            window_range,
            False,
            False,
        ),
        "override_preserved": thermostat.decide_cooling_strategy(
            Decimal("10"),
            Decimal("-5"),
            high,
            high_range,
            window,
            window_range,
            True,
            True,
        ),
    }

    return {
        name: describe_cooling_decision(decision)
        for name, decision in cases.items()
    }


def simulate_fan(thermostat, clock):
    reset_controller_state(thermostat, clock, thermostat.GPIO)
    temps = [Decimal("26.3"), Decimal("23.7")] * 16
    max_range = Decimal("0")
    for temp in temps:
        thermostat.ventilation_control(temp, Decimal("25"), Decimal("2"), False)
        max_range = max(
            max_range,
            thermostat.dynamic_hysteresis_range("fan", Decimal("2")),
        )
        clock.advance(130)
    return {
        "changes": len(thermostat.ACTUATOR_STATE["fan"]["changes"]),
        "possible_changes_without_widening": len(temps),
        "max_effective_range": str(max_range),
        "final_state": thermostat.ACTUATOR_STATE["fan"]["state"],
    }


def simulate_window(thermostat, clock):
    reset_controller_state(thermostat, clock, thermostat.GPIO)
    temps = [Decimal("26.3"), Decimal("23.7")] * 10
    max_range = Decimal("0")
    for temp in temps:
        thermostat.window_control(temp, Decimal("25"), Decimal("2"), False)
        max_range = max(
            max_range,
            thermostat.dynamic_hysteresis_range("window", Decimal("2")),
        )
        clock.advance(310)
    return {
        "changes": len(thermostat.ACTUATOR_STATE["window"]["changes"]),
        "possible_changes_without_widening": len(temps),
        "max_effective_range": str(max_range),
        "final_db_state": scalar("SELECT window FROM status WHERE id=1"),
    }


def test_overrides(thermostat, clock):
    reset_controller_state(thermostat, clock, thermostat.GPIO)
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            cur.execute(
                """
                UPDATE overrides
                SET fanoverride=1, fanexpire=%s,
                    windowoverride=1, windowexpire=%s
                WHERE id=1
                """,
                (future, future),
            )
    finally:
        con.close()

    overrides = thermostat.get_override_settings()
    thermostat.ventilation_control(
        Decimal("10"), Decimal("25"), Decimal("2"), overrides["fan"]
    )
    thermostat.window_control(
        Decimal("10"), Decimal("25"), Decimal("2"), overrides["window"]
    )
    return {
        "overrides": overrides,
        "fan_state": thermostat.ACTUATOR_STATE["fan"]["state"],
        "window_db_state": scalar("SELECT window FROM status WHERE id=1"),
    }


def simulate_day_night_cycle(thermostat, clock):
    reset_controller_state(thermostat, clock, thermostat.GPIO)
    settings = thermostat.get_schedule_settings()
    temps = []

    for step in range(96):
        radians = (2 * math.pi * step / 96) - (math.pi / 2)
        temp = Decimal(str(round(-15 + ((math.sin(radians) + 1) / 2) * 53, 2)))
        temps.append(temp)

        thermostat.cooling_control(
            temp,
            None,
            settings,
            {"fan": False, "window": False},
        )
        thermostat.heater_control(
            temp,
            settings["lowtemp"],
            settings["lowtemprange"],
        )
        clock.advance(15 * 60)

    return {
        "min_temp": str(min(temps)),
        "max_temp": str(max(temps)),
        "heater_gpio_outputs": sum(
            1
            for event in thermostat.GPIO.events
            if len(event) >= 4
            and event[1] == "output"
            and event[2] == thermostat.HEATER_GPIO
        ),
        "fan_gpio_outputs": sum(
            1
            for event in thermostat.GPIO.events
            if len(event) >= 4
            and event[1] == "output"
            and event[2] in {thermostat.VENT_FAN_GPIO, thermostat.AUX_VENT_FAN_GPIO}
        ),
        "window_gpio_outputs": sum(
            1
            for event in thermostat.GPIO.events
            if len(event) >= 4
            and event[1] == "output"
            and event[2] in {
                thermostat.WINDOW_GPIO,
                thermostat.WINDOW_REVERSER_GPIO,
                thermostat.ROOF_GPIO,
                thermostat.ROOF_REVERSER_GPIO,
            }
        ),
        "final_heater_state": thermostat.ACTUATOR_STATE["heater"]["state"],
        "final_fan_state": thermostat.ACTUATOR_STATE["fan"]["state"],
        "final_window_db_state": scalar("SELECT window FROM status WHERE id=1"),
    }


def simulate_solar_greenhouse_cycle(thermostat, clock):
    reset_controller_state(thermostat, clock, thermostat.GPIO)
    inside_temps = []
    outside_temps = []
    widened = {
        "heater": Decimal("0"),
        "fan": Decimal("0"),
        "window": Decimal("0"),
    }

    for step in range(96):
        sim_seconds = step * 15 * 60
        radians = (2 * math.pi * step / 96) - (math.pi / 2)
        outside = Decimal(str(round(-15 + ((math.sin(radians) + 1) / 2) * 54, 2)))
        inside = Decimal(str(round(1 + ((math.sin(radians) + 1) / 2) * 44, 2)))

        outside_temps.append(outside)
        inside_temps.append(inside)
        update_currenttemps(inside, outside)

        current_temp = thermostat.select_working_temperature(
            thermostat.get_sensor_data()
        )
        settings = simulated_schedule_settings(sim_seconds)

        thermostat.cooling_control(
            current_temp,
            outside,
            settings,
            {"fan": False, "window": False},
        )
        thermostat.heater_control(
            current_temp,
            settings["lowtemp"],
            settings["lowtemprange"],
        )

        widened["heater"] = max(
            widened["heater"],
            thermostat.dynamic_hysteresis_range(
                "heater", settings["lowtemprange"]
            ),
        )
        widened["fan"] = max(
            widened["fan"],
            thermostat.dynamic_hysteresis_range(
                "fan", settings["hightemprange"]
            ),
        )
        widened["window"] = max(
            widened["window"],
            thermostat.dynamic_hysteresis_range(
                "window", settings["windowtemprange"]
            ),
        )
        clock.advance(15 * 60)

    return {
        "outside_min": str(min(outside_temps)),
        "outside_max": str(max(outside_temps)),
        "inside_min": str(min(inside_temps)),
        "inside_max": str(max(inside_temps)),
        "heater_changes_recent": len(thermostat.ACTUATOR_STATE["heater"]["changes"]),
        "fan_changes_recent": len(thermostat.ACTUATOR_STATE["fan"]["changes"]),
        "window_changes_recent": len(thermostat.ACTUATOR_STATE["window"]["changes"]),
        "heater_gpio_outputs": sum(
            1
            for event in thermostat.GPIO.events
            if len(event) >= 4
            and event[1] == "output"
            and event[2] == thermostat.HEATER_GPIO
        ),
        "fan_gpio_outputs": sum(
            1
            for event in thermostat.GPIO.events
            if len(event) >= 4
            and event[1] == "output"
            and event[2] in {thermostat.VENT_FAN_GPIO, thermostat.AUX_VENT_FAN_GPIO}
        ),
        "window_gpio_outputs": sum(
            1
            for event in thermostat.GPIO.events
            if len(event) >= 4
            and event[1] == "output"
            and event[2] in {
                thermostat.WINDOW_GPIO,
                thermostat.WINDOW_REVERSER_GPIO,
                thermostat.ROOF_GPIO,
                thermostat.ROOF_REVERSER_GPIO,
            }
        ),
        "max_effective_ranges": {k: str(v) for k, v in widened.items()},
        "final_heater_state": thermostat.ACTUATOR_STATE["heater"]["state"],
        "final_fan_state": thermostat.ACTUATOR_STATE["fan"]["state"],
        "final_window_db_state": scalar("SELECT window FROM status WHERE id=1"),
    }


def test_cloud_flicker_threshold_hover(thermostat, clock):
    reset_controller_state(thermostat, clock, thermostat.GPIO)
    settings = simulated_schedule_settings(12 * 3600)

    fan_high = settings["hightemp"]
    fan_range = settings["hightemprange"]
    window_target = settings["windowtemp"]
    window_range = settings["windowtemprange"]

    fan_temps = [
        fan_high + (fan_range / 2) + Decimal("0.4"),
        fan_high - (fan_range / 2) - Decimal("0.4"),
    ] * 18

    max_fan_range = Decimal("0")
    for temp in fan_temps:
        thermostat.ventilation_control(temp, fan_high, fan_range, False)
        max_fan_range = max(
            max_fan_range,
            thermostat.dynamic_hysteresis_range("fan", fan_range),
        )
        clock.advance(130)

    fan_changes = len(thermostat.ACTUATOR_STATE["fan"]["changes"])

    thermostat.ACTUATOR_STATE["window"]["state"] = False
    thermostat.ACTUATOR_STATE["window"]["last_change"] = 0.0
    thermostat.ACTUATOR_STATE["window"]["last_direction"] = None
    thermostat.ACTUATOR_STATE["window"]["changes"] = []
    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            cur.execute("UPDATE status SET window=0 WHERE id=1")
    finally:
        con.close()

    window_temps = [
        window_target + (window_range / 2) + Decimal("0.4"),
        window_target - (window_range / 2) - Decimal("0.4"),
    ] * 12

    max_window_range = Decimal("0")
    for temp in window_temps:
        thermostat.window_control(temp, window_target, window_range, False)
        max_window_range = max(
            max_window_range,
            thermostat.dynamic_hysteresis_range("window", window_range),
        )
        clock.advance(310)

    return {
        "settings_used": {
            "hightemp": str(fan_high),
            "hightemprange": str(fan_range),
            "windowtemp": str(window_target),
            "windowtemprange": str(window_range),
        },
        "fan_changes": fan_changes,
        "fan_possible_flips": len(fan_temps),
        "fan_max_effective_range": str(max_fan_range),
        "window_changes": len(thermostat.ACTUATOR_STATE["window"]["changes"]),
        "window_possible_flips": len(window_temps),
        "window_max_effective_range": str(max_window_range),
        "final_fan_state": thermostat.ACTUATOR_STATE["fan"]["state"],
        "final_window_db_state": scalar("SELECT window FROM status WHERE id=1"),
    }


def test_cold_night_heater_stress(thermostat, clock):
    reset_controller_state(thermostat, clock, thermostat.GPIO)
    settings = simulated_schedule_settings(2 * 3600)
    low = settings["lowtemp"]
    low_range = settings["lowtemprange"]

    temps = [
        low - (low_range / 2) - Decimal("0.3"),
        low + (low_range / 2) + Decimal("0.3"),
    ] * 18

    max_range = Decimal("0")
    for temp in temps:
        thermostat.heater_control(temp, low, low_range)
        max_range = max(
            max_range,
            thermostat.dynamic_hysteresis_range("heater", low_range),
        )
        clock.advance(180)

    return {
        "settings_used": {
            "lowtemp": str(low),
            "lowtemprange": str(low_range),
        },
        "heater_changes": len(thermostat.ACTUATOR_STATE["heater"]["changes"]),
        "possible_flips": len(temps),
        "max_effective_range": str(max_range),
        "final_heater_state": thermostat.ACTUATOR_STATE["heater"]["state"],
    }


def test_partial_sensor_failure(thermostat, clock, gpio):
    reset_controller_state(thermostat, clock, gpio)
    now = datetime.now(timezone.utc)
    stale = now - timedelta(minutes=10)

    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            cur.execute("UPDATE currenttemp SET timestamp=%s", (stale,))
            cur.execute(
                """
                UPDATE currenttemp
                SET temperature=12.50,
                    temperatureF=54.50,
                    timestamp=%s
                WHERE Name='FrontTemp'
                """,
                (now,),
            )
            cur.execute(
                """
                UPDATE currenttemp
                SET temperature=10.50,
                    temperatureF=50.90,
                    timestamp=%s
                WHERE Name='BackTemp'
                """,
                (now,),
            )
    finally:
        con.close()

    sensors = thermostat.get_sensor_data()
    selected = thermostat.select_working_temperature(sensors)

    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            cur.execute(
                """
                UPDATE currenttemp
                SET timestamp=%s
                WHERE Name='FrontTemp'
                """,
                (stale,),
            )
    finally:
        con.close()

    sensors_after_front_stale = thermostat.get_sensor_data()
    selected_after_front_stale = thermostat.select_working_temperature(
        sensors_after_front_stale
    )

    return {
        "average_age_fresh": sensors["AverageInsideTemp"]["age"]
        <= thermostat.MAX_SENSOR_AGE_SECONDS,
        "front_age_fresh": sensors["FrontTemp"]["age"]
        <= thermostat.MAX_SENSOR_AGE_SECONDS,
        "selected_when_average_stale": str(selected),
        "selected_when_average_and_front_stale": str(selected_after_front_stale),
        "cleanup_called": gpio.cleanup_called,
    }


def test_outside_temperature_selection(thermostat, clock, gpio):
    reset_controller_state(thermostat, clock, gpio)
    update_currenttemps(Decimal("20.0"), Decimal("-4.5"))

    fresh = thermostat.select_outside_temperature(thermostat.get_sensor_data())

    stale = datetime.now(timezone.utc) - timedelta(minutes=10)
    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            cur.execute(
                """
                UPDATE currenttemp
                SET timestamp=%s
                WHERE Name='OutsideTemp'
                """,
                (stale,),
            )
    finally:
        con.close()

    stale_result = thermostat.select_outside_temperature(
        thermostat.get_sensor_data()
    )

    return {
        "fresh_outside_temp": str(fresh),
        "stale_outside_temp_falls_back": stale_result is None,
    }


def test_safe_shutdown(thermostat, clock, gpio):
    reset_controller_state(thermostat, clock, gpio)
    old = datetime.now(timezone.utc) - timedelta(hours=2)
    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            cur.execute("UPDATE currenttemp SET timestamp=%s", (old,))
    finally:
        con.close()

    try:
        thermostat.select_working_temperature(thermostat.get_sensor_data())
    except SystemExit as exc:
        return {
            "exited": True,
            "exit_code": exc.code,
            "cleanup_called": gpio.cleanup_called,
            "window_db_state": scalar("SELECT window FROM status WHERE id=1"),
            "high_pins_after": sorted(
                pin for pin, state in gpio.pin_state.items() if state == gpio.HIGH
            ),
        }

    return {"exited": False}


def test_mariadb_outage_mid_loop(thermostat, clock, gpio):
    reset_controller_state(thermostat, clock, gpio)
    gpio.pin_state[thermostat.HEATER_GPIO] = gpio.HIGH
    gpio.pin_state[thermostat.VENT_FAN_GPIO] = gpio.HIGH
    gpio.pin_state[thermostat.AUX_VENT_FAN_GPIO] = gpio.HIGH

    old_db_name = thermostat.DB_NAME
    thermostat.DB_NAME = f"{TEST_DB}_missing"

    try:
        try:
            thermostat.get_sensor_data()
        except Exception:
            thermostat.shutdownnow()
    except SystemExit as exc:
        return {
            "exited": True,
            "exit_code": exc.code,
            "cleanup_called": gpio.cleanup_called,
            "high_pins_after": sorted(
                pin for pin, state in gpio.pin_state.items() if state == gpio.HIGH
            ),
        }
    finally:
        thermostat.DB_NAME = old_db_name

    return {"exited": False}


def test_override_expiration(thermostat, clock):
    reset_controller_state(thermostat, clock, thermostat.GPIO)
    now = datetime.now(timezone.utc)
    past = now - timedelta(seconds=1)
    future = now + timedelta(minutes=10)

    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            cur.execute(
                """
                UPDATE overrides
                SET fanoverride=1,
                    fanexpire=%s,
                    windowoverride=1,
                    windowexpire=%s
                WHERE id=1
                """,
                (past, past),
            )
    finally:
        con.close()

    expired = thermostat.get_override_settings()

    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            cur.execute(
                """
                UPDATE overrides
                SET fanoverride=1,
                    fanexpire=%s,
                    windowoverride=1,
                    windowexpire=%s
                WHERE id=1
                """,
                (future, future),
            )
    finally:
        con.close()

    active = thermostat.get_override_settings()
    thermostat.ventilation_control(
        Decimal("10"), Decimal("36"), Decimal("4"), active["fan"]
    )
    thermostat.window_control(
        Decimal("10"), Decimal("33"), Decimal("6"), active["window"]
    )

    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            cur.execute(
                """
                UPDATE overrides
                SET fanexpire=%s,
                    windowexpire=%s
                WHERE id=1
                """,
                (past, past),
            )
    finally:
        con.close()

    expired_after_active = thermostat.get_override_settings()

    return {
        "expired": expired,
        "active": active,
        "expired_after_active": expired_after_active,
        "fan_state_after_active_override": thermostat.ACTUATOR_STATE["fan"]["state"],
        "window_state_after_active_override": scalar(
            "SELECT window FROM status WHERE id=1"
        ),
    }


def test_sigterm_shutdown(thermostat, clock, gpio):
    reset_controller_state(thermostat, clock, gpio)
    gpio.pin_state[thermostat.HEATER_GPIO] = gpio.HIGH
    gpio.pin_state[thermostat.VENT_FAN_GPIO] = gpio.HIGH

    try:
        thermostat.handle_shutdown_signal(signal.SIGTERM, None)
    except SystemExit as exc:
        return {
            "exited": True,
            "exit_code": exc.code,
            "cleanup_called": gpio.cleanup_called,
            "window_db_state": scalar("SELECT window FROM status WHERE id=1"),
            "high_pins_after": sorted(
                pin for pin, state in gpio.pin_state.items() if state == gpio.HIGH
            ),
        }

    return {"exited": False}


def test_startup_state(thermostat, clock, gpio):
    reset_controller_state(thermostat, clock, gpio)
    outputs = {
        thermostat.WINDOW_REVERSER_GPIO,
        thermostat.WINDOW_GPIO,
        thermostat.ROOF_REVERSER_GPIO,
        thermostat.ROOF_GPIO,
        thermostat.VENT_FAN_GPIO,
        thermostat.AUX_VENT_FAN_GPIO,
        thermostat.HEATER_GPIO,
        thermostat.CIRC_FAN_GPIO,
        thermostat.UNUSED_GPIO_1,
        thermostat.UNUSED_GPIO_2,
        thermostat.UNUSED_GPIO_3,
    }

    for pin in outputs:
        gpio.pin_state[pin] = gpio.HIGH

    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            cur.execute("UPDATE status SET window=1 WHERE id=1")
    finally:
        con.close()

    thermostat.setup_gpio()
    high_after_setup = sorted(
        pin for pin, state in gpio.pin_state.items() if state == gpio.HIGH
    )
    window_state_after_setup = scalar("SELECT window FROM status WHERE id=1")

    thermostat.window_control(Decimal("40"), Decimal("33"), Decimal("6"), False)

    return {
        "all_outputs_low_after_setup": not high_after_setup,
        "high_pins_after_setup": high_after_setup,
        "window_db_state_after_setup": window_state_after_setup,
        "can_open_immediately_after_startup_close": scalar(
            "SELECT window FROM status WHERE id=1"
        )
        == 1,
        "window_changes_recorded": len(thermostat.ACTUATOR_STATE["window"]["changes"]),
    }


def test_empty_or_damaged_tables(thermostat, clock, gpio):
    reset_controller_state(thermostat, clock, gpio)
    results = {}

    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            cur.execute("DELETE FROM status")
            cur.execute("DELETE FROM overrides")
    finally:
        con.close()

    thermostat.ensure_singleton_rows()
    results["singleton_rows_repaired"] = {
        "status_count": scalar("SELECT COUNT(*) FROM status WHERE id=1"),
        "overrides_count": scalar("SELECT COUNT(*) FROM overrides WHERE id=1"),
    }

    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            cur.execute("DELETE FROM settings")
    finally:
        con.close()

    try:
        thermostat.get_schedule_settings()
        results["empty_settings"] = "unexpected_success"
    except RuntimeError as exc:
        results["empty_settings"] = str(exc)

    copy_live_settings()

    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            cur.execute("DELETE FROM currenttemp")
    finally:
        con.close()

    try:
        thermostat.select_working_temperature(thermostat.get_sensor_data())
        results["empty_currenttemp"] = {"exited": False}
    except SystemExit as exc:
        results["empty_currenttemp"] = {
            "exited": True,
            "exit_code": exc.code,
            "cleanup_called": gpio.cleanup_called,
            "high_pins_after": sorted(
                pin for pin, state in gpio.pin_state.items() if state == gpio.HIGH
            ),
        }

    seed_currenttemp_rows()
    return results


def test_strict_sql_mode():
    strict_db = f"{TEST_DB}_strict"
    schema = (SQL_DIR / "schema.sql").read_text()
    schema = schema.replace("`greenhouse`", f"`{strict_db}`")

    statements = []
    current = []
    for line in schema.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        current.append(line)
        if stripped.endswith(";"):
            stmt = "\n".join(current).rstrip(";")
            current = []
            upper = stmt.upper()
            if upper.startswith(("SET ", "START TRANSACTION", "COMMIT")):
                continue
            if upper.startswith(("CREATE USER", "GRANT ", "FLUSH PRIVILEGES")):
                continue
            statements.append(stmt)

    con = root_conn()
    try:
        with con.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS `{strict_db}`")
            cur.execute(
                """
                SET SESSION sql_mode =
                'STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO'
                """
            )
            for stmt in statements:
                cur.execute(stmt)

            cur.execute(
                f"""
                INSERT INTO `{strict_db}`.status_log
                (heater, fan, circfan, window)
                VALUES (0, 0, 0, 0)
                """
            )
            cur.execute(
                f"""
                INSERT INTO `{strict_db}`.sensor_diagnostics
                (sensor_name, timestamp, raw_values, crc_failures, notes)
                VALUES ('StrictSensor', NOW(), '20.0,20.1', 0, 'ok')
                """
            )
            cur.execute(f"SELECT COUNT(*) FROM `{strict_db}`.status")
            status_count = cur.fetchone()[0]
            cur.execute(f"DROP DATABASE IF EXISTS `{strict_db}`")

        return {
            "schema_imported": True,
            "runtime_inserts_ok": True,
            "status_rows": status_count,
        }
    except Exception as exc:
        with root_conn() as cleanup_con:
            with cleanup_con.cursor() as cur:
                cur.execute(f"DROP DATABASE IF EXISTS `{strict_db}`")
        return {
            "schema_imported": False,
            "runtime_inserts_ok": False,
            "error": repr(exc),
        }


def insert_diag(cur, sensor, rows, raw, crc=0, notes="ok"):
    now = datetime.now(timezone.utc)
    for offset in range(rows):
        cur.execute(
            """
            INSERT INTO sensor_diagnostics
            (sensor_name, timestamp, raw_values, median, average, crc_failures, notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            """,
            (sensor, now - timedelta(minutes=offset * 5), raw, None, None, crc, notes),
        )


def test_sensor_health(sensor_health):
    clear_sensor_health_tables()
    sensor_health.ALERTS_ENABLED = True
    sent = []

    def fake_send(subject, body):
        sent.append((subject, body))

    sensor_health.send_email = fake_send

    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            insert_diag(cur, "HealthySensor", 3, "20.0,20.1,20.0,20.1", 0, "ok")
            insert_diag(cur, "NoisyCrcSensor", 3, "12,30,14,29,15,28,16,27", 2, "ok")
            insert_diag(cur, "FailedSensor", 3, "FAIL", -1, "FAILED")
            insert_diag(cur, "FlatlineSensor", 3, "22.0,22.0,22.0,22.0", 0, "ok")
    finally:
        con.close()

    sensor_health.main()

    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            cur.execute(
                """
                SELECT sensor_name, health_score, status, notes
                FROM sensor_health
                ORDER BY sensor_name
                """
            )
            rows = cur.fetchall()
            cur.execute("SELECT sensor_name, alert_type FROM sensor_alerts ORDER BY sensor_name")
            alerts = cur.fetchall()
    finally:
        con.close()

    return {
        "health_rows": rows,
        "alert_rows": alerts,
        "send_email_calls": len(sent),
    }


def test_ds18b20_weird_values(sensor_health):
    clear_sensor_health_tables()
    sensor_health.ALERTS_ENABLED = True
    sent = []

    def fake_send(subject, body):
        sent.append((subject, body))

    sensor_health.send_email = fake_send

    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            insert_diag(cur, "PowerOn85Sensor", 3, "85.0,85.0,85.0,85.0", 0, "ok")
            insert_diag(
                cur,
                "DisconnectedMinus127Sensor",
                3,
                "-127.0,-127.0,-127.0,-127.0",
                0,
                "ok",
            )
            insert_diag(
                cur,
                "MixedSentinelSensor",
                3,
                "20.0,20.1,85.0,20.2,-127.0,20.0",
                0,
                "ok",
            )
    finally:
        con.close()

    sensor_health.main()

    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            cur.execute(
                """
                SELECT sensor_name, health_score, status, notes
                FROM sensor_health
                ORDER BY sensor_name
                """
            )
            health_rows = cur.fetchall()
            cur.execute(
                """
                SELECT sensor_name, alert_type
                FROM sensor_alerts
                ORDER BY sensor_name
                """
            )
            alert_rows = cur.fetchall()
    finally:
        con.close()

    return {
        "health_rows": health_rows,
        "alert_rows": alert_rows,
        "send_email_calls": len(sent),
    }


def test_alert_cooldown(sensor_health):
    clear_sensor_health_tables()
    sensor_health.ALERTS_ENABLED = True
    sensor_health.ALERT_COOLDOWN_HOURS = 6
    sent = []

    def fake_send(subject, body):
        sent.append((subject, body))

    sensor_health.send_email = fake_send

    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            insert_diag(cur, "CooldownSensor", 3, "FAIL", -1, "FAILED")
    finally:
        con.close()

    sensor_health.main()
    first_count = len(sent)
    sensor_health.main()
    second_count = len(sent)

    old_alert_time = datetime.now(timezone.utc) - timedelta(hours=7)
    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            cur.execute(
                """
                UPDATE sensor_alerts
                SET timestamp=%s
                WHERE sensor_name='CooldownSensor'
                """,
                (old_alert_time,),
            )
    finally:
        con.close()

    sensor_health.main()
    third_count = len(sent)

    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            cur.execute(
                """
                SELECT sensor_name, alert_type, COUNT(*)
                FROM sensor_alerts
                GROUP BY sensor_name, alert_type
                """
            )
            alert_rows = cur.fetchall()
    finally:
        con.close()

    return {
        "emails_after_first_run": first_count,
        "emails_after_second_run_within_cooldown": second_count,
        "emails_after_cooldown_expired": third_count,
        "alert_rows": alert_rows,
    }


def main():
    execute_schema()
    thermostat, sensor_health, _read_sensors, clock, gpio = patch_modules()

    results = {
        "decision_helpers": test_decision_helpers(thermostat),
        "outside_aware_cooling_strategy": test_outside_aware_cooling_strategy(
            thermostat
        ),
        "day_night_cycle": simulate_day_night_cycle(thermostat, clock),
        "solar_greenhouse_cycle_live_settings": simulate_solar_greenhouse_cycle(
            thermostat, clock
        ),
        "cloud_flicker_threshold_hover": test_cloud_flicker_threshold_hover(
            thermostat, clock
        ),
        "cold_night_heater_stress": test_cold_night_heater_stress(
            thermostat, clock
        ),
        "heater_dynamic": simulate_heater(thermostat, clock),
        "fan_dynamic": simulate_fan(thermostat, clock),
        "window_dynamic": simulate_window(thermostat, clock),
        "partial_sensor_failure": test_partial_sensor_failure(
            thermostat, clock, gpio
        ),
        "outside_temperature_selection": test_outside_temperature_selection(
            thermostat, clock, gpio
        ),
        "overrides": test_overrides(thermostat, clock),
        "override_expiration": test_override_expiration(thermostat, clock),
        "safe_shutdown": test_safe_shutdown(thermostat, clock, gpio),
        "mariadb_outage_mid_loop": test_mariadb_outage_mid_loop(
            thermostat, clock, gpio
        ),
        "sigterm_systemd_shutdown": test_sigterm_shutdown(
            thermostat, clock, gpio
        ),
        "pi_reboot_startup_state": test_startup_state(thermostat, clock, gpio),
        "empty_or_damaged_tables": test_empty_or_damaged_tables(
            thermostat, clock, gpio
        ),
        "strict_sql_mode": test_strict_sql_mode(),
        "sensor_health": test_sensor_health(sensor_health),
        "ds18b20_weird_values": test_ds18b20_weird_values(sensor_health),
        "alert_cooldown": test_alert_cooldown(sensor_health),
    }

    con = root_conn()
    try:
        with con.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS `{TEST_DB}`")
    finally:
        con.close()

    for name, result in results.items():
        print(f"\n{name}")
        print(result)


if __name__ == "__main__":
    main()
