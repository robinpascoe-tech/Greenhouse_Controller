#!/usr/bin/env python3
"""
Read-only terminal monitor for the greenhouse GPIO outputs.

The controller owns GPIO writes. This helper only calls `pinctrl get` and shows
the configured pins in a curses UI for troubleshooting relay state.
"""

import curses
import subprocess
import time
from datetime import datetime


# ============================================================
# GPIO MAP
# ============================================================

GPIO_MAP = {
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

WATCH_PINS = set(GPIO_MAP.values())


# ============================================================
# GPIO READING
# ============================================================

def read_all_gpio():
    """Return the current state of monitored GPIO pins as {pin: 0/1}."""
    try:
        output = subprocess.check_output(["pinctrl", "get"], text=True)
    except Exception:
        return {}

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

        # pinctrl output includes state text such as "hi" or "lo".
        states[pin] = 1 if " hi " in line or "| hi" in line or line.endswith("hi") else 0

    return states


# ============================================================
# TERMINAL UI
# ============================================================

def bar(state):
    """Draw a compact ASCII state indicator."""
    return "[##########]" if state else "[          ]"


def draw_header(stdscr):
    stdscr.addstr(0, 0, "GREENHOUSE GPIO MONITOR (READ ONLY)", curses.A_BOLD)
    stdscr.addstr(1, 0, "=" * 80)
    stdscr.addstr(2, 0, f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    stdscr.addstr(4, 0, "DEVICE")
    stdscr.addstr(4, 30, "GPIO")
    stdscr.addstr(4, 40, "STATE")
    stdscr.addstr(4, 55, "GRAPHICAL")
    stdscr.addstr(5, 0, "-" * 80)


def monitor(stdscr):
    curses.curs_set(0)

    while True:
        stdscr.clear()
        draw_header(stdscr)

        gpio_states = read_all_gpio()
        row = 7
        active = []

        for name, pin in GPIO_MAP.items():
            state = gpio_states.get(pin, 0)

            if state:
                active.append(name)

            attr = curses.A_BOLD if state else curses.A_DIM

            stdscr.addstr(row, 0, name.ljust(28), attr)
            stdscr.addstr(row, 30, str(pin).ljust(5), attr)
            stdscr.addstr(row, 40, "ON" if state else "OFF", attr)
            stdscr.addstr(row, 55, bar(state), attr)

            row += 1

        row += 2
        stdscr.addstr(row, 0, "ACTIVE OUTPUTS:", curses.A_BOLD)
        row += 1

        if active:
            for name in active:
                stdscr.addstr(row, 2, f"- {name}")
                row += 1
        else:
            stdscr.addstr(row, 2, "None")

        row += 2
        stdscr.addstr(row, 0, "Press CTRL+C to exit.", curses.A_DIM)

        stdscr.refresh()
        time.sleep(1)


def main():
    try:
        curses.wrapper(monitor)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
