#!/usr/bin/env python3
"""
Real GPIO integration test for greenhouse_controller.py.

This is a middle layer between the pure simulation harness and a live
greenhouse soak test. It intentionally drives the Raspberry Pi GPIO outputs,
but it uses a throwaway MariaDB database and shortened relay timing so the test
can verify pin behavior without depending on real sensors.

Safety guard:
    GREENHOUSE_ALLOW_REAL_GPIO_TEST=1 must be set or this script exits.

Database setup:
    GREENHOUSE_TEST_DB_ROOT_PASSWORD must be set so the script can create and
    drop a throwaway database.
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pymysql


TEST_DB = "greenhouse_gpio_integration_test"
ALLOW_FLAG = "GREENHOUSE_ALLOW_REAL_GPIO_TEST"
ROOT_PASSWORD_ENV = "GREENHOUSE_TEST_DB_ROOT_PASSWORD"
SETTLE_SECONDS = 0.04
FAST_SLEEP_SECONDS = 0.02
REAL_SLEEP = time.sleep

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
SQL_DIR = PROJECT_ROOT / "sql"


GPIO_NAMES = {
    "WINDOW_REVERSER": 22,
    "WINDOW_MOTOR": 17,
    "ROOF_REVERSER": 9,
    "ROOF_MOTOR": 10,
    "VENT_FAN": 5,
    "AUX_VENT_FAN": 11,
    "HEATER": 19,
    "CIRC_FAN": 6,
    "UNUSED_1": 13,
    "UNUSED_2": 26,
    "UNUSED_3": 27,
}

WATCH_PINS = set(GPIO_NAMES.values())


class TestFailure(Exception):
    """Raised when a real GPIO integration assertion fails."""


class GPIOProbe:
    """
    RPi.GPIO wrapper that writes real GPIO and samples state with pinctrl.

    The controller still owns GPIO writes. This wrapper records the independent
    observed state after each write so the test can verify actual pin levels.
    """

    def __init__(self, gpio_module):
        self._gpio = gpio_module
        self.events = []

        self.BCM = gpio_module.BCM
        self.OUT = gpio_module.OUT
        self.HIGH = gpio_module.HIGH
        self.LOW = gpio_module.LOW

    def __getattr__(self, name):
        return getattr(self._gpio, name)

    def setmode(self, mode):
        return self._gpio.setmode(mode)

    def setwarnings(self, enabled):
        return self._gpio.setwarnings(enabled)

    def setup(self, pin, mode):
        result = self._gpio.setup(pin, mode)
        self.events.append(("setup", pin, mode, self.read_pin(pin)))
        return result

    def output(self, pin, state):
        result = self._gpio.output(pin, state)
        REAL_SLEEP(SETTLE_SECONDS)
        observed = self.read_pin(pin)
        self.events.append(("output", pin, int(state), observed))
        return result

    def cleanup(self):
        self.events.append(("cleanup", None, None, None))
        return self._gpio.cleanup()

    def read_all(self):
        return read_all_gpio()

    def read_pin(self, pin):
        return read_all_gpio().get(pin)


def require_safety_flags():
    """Require explicit operator consent before touching real GPIO."""
    if os.environ.get(ALLOW_FLAG) != "1":
        raise SystemExit(
            f"Refusing to drive real GPIO. Set {ALLOW_FLAG}=1 to run."
        )

    if not os.environ.get(ROOT_PASSWORD_ENV):
        raise SystemExit(
            f"Set {ROOT_PASSWORD_ENV} so the test can create a throwaway database."
        )


def root_conn(db=None, autocommit=True):
    """Open a MariaDB root connection for throwaway test database setup."""
    return pymysql.connect(
        host="localhost",
        user="root",
        password=os.environ[ROOT_PASSWORD_ENV],
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


def drop_test_db():
    """Drop the throwaway test database."""
    con = root_conn()
    try:
        with con.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS `{TEST_DB}`")
    finally:
        con.close()


def read_all_gpio():
    """Return current monitored GPIO states as {pin: 0/1} using pinctrl."""
    try:
        output = subprocess.check_output(["pinctrl", "get"], text=True)
    except Exception as exc:
        raise TestFailure(f"Could not read GPIO state with pinctrl: {exc}") from exc

    states = {}

    for line in output.splitlines():
        line = line.strip().lower()

        if ":" not in line:
            continue

        try:
            pin = int(line.split(":", 1)[0])
        except ValueError:
            continue

        if pin not in WATCH_PINS:
            continue

        states[pin] = 1 if " hi " in line or "| hi" in line or line.endswith("hi") else 0

    return states


def status_row():
    """Return the singleton runtime status row from the throwaway database."""
    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            cur.execute("SELECT heater, fan, circfan, window FROM status WHERE id=1")
            return cur.fetchone()
    finally:
        con.close()


def seed_current_temps(inside=Decimal("20.0"), outside=Decimal("10.0")):
    """Seed fresh sensor readings for controller helper calls."""
    now = datetime.now(timezone.utc)
    con = root_conn(TEST_DB)
    try:
        with con.cursor() as cur:
            for name, value in (
                ("BackTemp", inside),
                ("FrontTemp", inside),
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


def assert_pin(probe, name, expected):
    pin = GPIO_NAMES[name]
    observed = probe.read_pin(pin)

    if observed != expected:
        raise TestFailure(
            f"{name} GPIO {pin} expected {expected}, observed {observed}"
        )


def assert_all_low(probe):
    states = probe.read_all()
    high = {
        name: pin
        for name, pin in GPIO_NAMES.items()
        if states.get(pin) == 1
    }

    if high:
        raise TestFailure(f"Expected all monitored GPIO LOW, found HIGH: {high}")


def reset_actuator_memory(controller):
    """Reset in-memory actuator state between direct control checks."""
    for name, state in controller.ACTUATOR_STATE.items():
        state["state"] = False
        state["last_change"] = 0.0
        state["changes"] = []
        if name == "window":
            state["last_direction"] = None


def load_controller():
    """Import controller and point it at the throwaway database."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    controller = importlib.import_module("greenhouse_controller")

    controller.DB_HOST = "localhost"
    controller.DB_USER = "root"
    controller.DB_PASSWORD = os.environ[ROOT_PASSWORD_ENV]
    controller.DB_NAME = TEST_DB

    original_gpio = controller.GPIO
    probe = GPIOProbe(original_gpio)
    controller.GPIO = probe

    def fast_sleep(seconds):
        # Keep short pulses long enough for pinctrl observation, but avoid
        # full greenhouse actuator timing during this hardware test.
        REAL_SLEEP(min(float(seconds), FAST_SLEEP_SECONDS))

    controller.time.sleep = fast_sleep

    return controller, probe


def run_tests(controller, probe):
    """Run direct GPIO integration checks against the controller functions."""
    results = []

    def mark(name):
        results.append(name)
        print(f"PASS {name}")

    reset_actuator_memory(controller)
    controller.setup_gpio()
    assert_all_low(probe)
    mark("setup leaves monitored outputs LOW")

    controller.circulation_control(True)
    assert_pin(probe, "CIRC_FAN", 1)
    if status_row()[2] != 1:
        raise TestFailure("circulation_control(True) did not update status.circfan")
    controller.circulation_control(False)
    assert_pin(probe, "CIRC_FAN", 0)
    mark("circulation fan HIGH/LOW and SQL status")

    reset_actuator_memory(controller)
    controller.heater_control(Decimal("4.0"), Decimal("6.0"), Decimal("2.0"))
    assert_pin(probe, "HEATER", 1)
    if status_row()[0] != 1:
        raise TestFailure("heater ON did not update status.heater")
    controller.ACTUATOR_STATE["heater"]["last_change"] -= 3600
    controller.heater_control(Decimal("8.0"), Decimal("6.0"), Decimal("2.0"))
    assert_pin(probe, "HEATER", 0)
    mark("heater HIGH/LOW and SQL status")

    reset_actuator_memory(controller)
    controller.ventilation_control(
        Decimal("40.0"),
        Decimal("36.0"),
        Decimal("4.0"),
        False,
    )
    assert_pin(probe, "VENT_FAN", 1)
    assert_pin(probe, "AUX_VENT_FAN", 1)
    if status_row()[1] != 1:
        raise TestFailure("fan ON did not update status.fan")
    controller.ACTUATOR_STATE["fan"]["last_change"] -= 3600
    controller.ventilation_control(
        Decimal("30.0"),
        Decimal("36.0"),
        Decimal("4.0"),
        False,
    )
    assert_pin(probe, "VENT_FAN", 0)
    assert_pin(probe, "AUX_VENT_FAN", 0)
    mark("ventilation fans HIGH/LOW and SQL status")

    reset_actuator_memory(controller)
    controller.open_windows(force=True, record=True)
    assert_pin(probe, "WINDOW_MOTOR", 0)
    assert_pin(probe, "ROOF_MOTOR", 0)
    if status_row()[3] != 1:
        raise TestFailure("open_windows did not update status.window")
    if not any(
        event[0] == "output"
        and event[1] == GPIO_NAMES["WINDOW_MOTOR"]
        and event[2] == 1
        and event[3] == 1
        for event in probe.events
    ):
        raise TestFailure("WINDOW_MOTOR HIGH pulse was not observed")
    if not any(
        event[0] == "output"
        and event[1] == GPIO_NAMES["ROOF_MOTOR"]
        and event[2] == 1
        and event[3] == 1
        for event in probe.events
    ):
        raise TestFailure("ROOF_MOTOR HIGH pulse was not observed")
    controller.close_windows(force=True, record=True)
    assert_all_low(probe)
    if status_row()[3] != 0:
        raise TestFailure("close_windows did not update status.window")
    mark("window motor pulses and final LOW state")

    seed_current_temps(Decimal("42.0"), Decimal("-5.0"))
    sensors = controller.get_sensor_data()
    current = controller.select_working_temperature(sensors)
    outside = controller.select_outside_temperature(sensors)
    settings = controller.get_schedule_settings()
    overrides = controller.get_override_settings()
    cooling = controller.get_cooling_decision(current, outside, settings, overrides)
    if cooling.strategy != "cold_outside_fan_preferred":
        raise TestFailure(f"Unexpected adaptive cooling strategy: {cooling.strategy}")
    mark("adaptive cooling decision uses fresh outside temperature")

    return results


def main():
    require_safety_flags()
    execute_schema()

    controller = None
    probe = None

    try:
        controller, probe = load_controller()
        results = run_tests(controller, probe)
        print(f"\nGPIO integration test passed ({len(results)} checks).")
    finally:
        if controller and probe:
            try:
                controller.GPIO.output(controller.VENT_FAN_GPIO, controller.GPIO.LOW)
                controller.GPIO.output(controller.AUX_VENT_FAN_GPIO, controller.GPIO.LOW)
                controller.GPIO.output(controller.CIRC_FAN_GPIO, controller.GPIO.LOW)
                controller.GPIO.output(controller.HEATER_GPIO, controller.GPIO.LOW)
                controller.GPIO.output(controller.UNUSED_GPIO_1, controller.GPIO.LOW)
                controller.GPIO.output(controller.UNUSED_GPIO_2, controller.GPIO.LOW)
                controller.GPIO.output(controller.UNUSED_GPIO_3, controller.GPIO.LOW)
                controller.close_windows(force=True, record=False)
                assert_all_low(probe)
            finally:
                controller.GPIO.cleanup()

        drop_test_db()


if __name__ == "__main__":
    main()
