# Greenhouse Controller Engineering Overview

This document explains how the greenhouse control system is organized, how data
moves through it, and where safety decisions are made.

## Goals

The project controls a Raspberry Pi based greenhouse automation system using
MariaDB as the shared state store. The controller reads recent temperature data,
applies schedule and override rules, and drives GPIO outputs for heating,
ventilation fans, circulation fan, and motorized windows.

The code favors simple, inspectable behavior over hidden automation. Most state
is stored in SQL tables so the controller, sensor reader, dashboard, and helper
scripts can all agree on the current greenhouse state.

## Repository Layout

```text
scripts/
  greenhouse_controller.py   Main long-running controller loop.
  read_sensors.py            Reads DS18B20 sensors and updates SQL.
  sensor_health.py           Scores sensor quality from diagnostic history.
  cleanup_status_log.py      Deletes old status_log rows.
  cleanup_sensor_diagnostics.py
                             Deletes old raw sensor diagnostic rows.

tools/
  simulation_harness.py      Deterministic controller simulation/test harness.
  simulate_sensors.py        Writes fake currenttemp values for development.
  gpio_monitor.py            Read-only terminal GPIO state monitor.

sql/
  schema.sql                 Fresh database schema.
  migrate_schema.sql         Migration for older greenhouse databases.

config/
  greenhouse.conf.example    Sanitized runtime configuration example.
  greenhouse-controller.service.example
                              Example systemd service unit.

docs/
  INSTALL.md
  ENGINEERING_OVERVIEW.md

html/
  Legacy PHP dashboard files.

archive/
  Historical notes and original Python 2 material.
```

## Runtime Data Flow

1. `read_sensors.py` reads each configured DS18B20 sensor from Linux 1-Wire
   files under `/sys/bus/w1/devices/.../w1_slave`.
2. Each sensor attempt is written to `sensor_diagnostics`, including failed
   reads. This is intentional: failure history is needed to detect degradation.
3. Clean operational readings are written to `currenttemp`.
4. `greenhouse_controller.py` reads `currenttemp`, chooses the best fresh inside
   temperature, loads the active schedule row from `settings`, checks
   `overrides`, and drives GPIO outputs.
5. The controller updates `status` as actuator states change.
6. When `status` changes, the controller appends a row to `status_log`.
7. `sensor_health.py` runs periodically, reads `sensor_diagnostics`, writes
   health snapshots to `sensor_health`, stores smoothing state in
   `sensor_state`, and records alerts in `sensor_alerts`.

## Database Tables

`currenttemp`
: The latest clean temperature values. The controller uses `AverageInsideTemp`
  first, then falls back to `FrontTemp`, then `BackTemp`.

`settings`
: Time-of-day temperature schedule. Each row includes high/low thresholds,
  hysteresis ranges, window thresholds, and circulation fan state.

`overrides`
: Singleton row used for temporary manual fan and window overrides. Overrides
  expire by timestamp.

`status`
: Singleton row representing current heater, fan, circulation fan, and window
  state.

`status_log`
: Historical actuator changes. Used for graphing and audit trails.

`sensor_diagnostics`
: Raw per-sensor diagnostic readings. Failed reads are stored here too. This
  table grows continuously until pruned.

`sensor_health`
: Derived sensor health scores and statuses.

`sensor_state`
: Per-sensor memory used for exponential moving average smoothing.

`sensor_alerts`
: Alert history and cooldown tracking.

`sensor_profile`
: Optional per-sensor tuning for expected temperature range and sensitivity.

## Temperature Selection

The main controller intentionally ignores stale readings. A sensor row is usable
only if its timestamp is recent enough. The priority order is:

1. `AverageInsideTemp`
2. `FrontTemp`
3. `BackTemp`

If none of those readings are fresh, the controller enters emergency shutdown:
fans and heater are turned off, windows are closed, GPIO cleanup is called, and
the process exits.

Outside temperature is recorded and useful for dashboards or future control
logic, but the current controller makes actuator decisions from inside
temperature only.

## Actuator Logic

### Heater

The heater uses low-temperature hysteresis:

```text
turn on  when current_temp <= lowtemp - (lowtemprange / 2)
turn off when current_temp >= lowtemp + (lowtemprange / 2)
```

Short-cycle protection enforces minimum on/off durations before state changes.

### Ventilation Fans

Ventilation fans use high-temperature hysteresis:

```text
turn on  when current_temp >= hightemp + (hightemprange / 2)
turn off when current_temp <= hightemp - (hightemprange / 2)
```

The controller starts the main fan, waits briefly, then starts the auxiliary
fan. Overrides can force the fans on until the override expiration time.

### Circulation Fan

The circulation fan follows the active schedule row directly. It is not tied to
temperature hysteresis.

### Windows

Windows use their own threshold and hysteresis range. The controller tracks
window state in SQL to avoid repeatedly issuing open/close sequences.

Window movement includes relay timing for the rear window and roof window. A
direction reversal lockout protects motors and relays from rapid open/close
direction changes.

## Short-Cycle Protection

The controller maintains recent actuator transition history in memory. If an
actuator changes too often within one hour, the controller temporarily widens
that actuator's hysteresis range.

This protects hardware from rapid cycling during noisy conditions such as:

- sun/cloud flicker around the fan or window thresholds
- heater overshoot around the low-temperature threshold
- greenhouse temperature quickly rebounding after fans/windows turn off

The widening never shrinks below the configured SQL range. It only adds a
temporary bonus when recent cycle counts exceed configured warning or severe
thresholds.

## Safety Behavior

The controller is fail-safe oriented:

- GPIO outputs are initialized LOW at startup.
- Windows are forced closed at startup without recording a normal cycle.
- `SIGTERM` and `KeyboardInterrupt` route through emergency shutdown.
- Emergency shutdown turns off heater/fans, closes windows, calls GPIO cleanup,
  and exits.
- Missing or stale inside sensor data causes emergency shutdown.
- Missing `status` or `overrides` singleton rows are repaired at startup.

## Sensor Health

`sensor_health.py` evaluates diagnostic history rather than only current
temperatures. It looks for:

- CRC instability
- high noise
- short-term and long-term drift
- flatline readings
- DS18B20 sentinel values such as `85.0 C` and `-127.0 C`
- total sensor failure rows

Health statuses include:

- `HEALTHY`
- `STABLE`
- `DEGRADED`
- `CRITICAL`
- `RECOVERED`
- `INSUFFICIENT_DATA`

Alerts are optional and disabled by default in the example config. When enabled,
alert history in `sensor_alerts` prevents repeated alerts inside the cooldown
window.

## Retention And Cleanup

`sensor_diagnostics` grows faster than the other tables because
`read_sensors.py` writes one row for every sensor attempt on every run. For
example, five sensors read once per minute creates 7,200 diagnostic rows per
day.

`sensor_health.py` currently uses 1-hour, 6-hour, and 24-hour windows, so it
does not need unlimited diagnostic history. The recommended cleanup script,
`scripts/cleanup_sensor_diagnostics.py`, keeps 30 days by default.

`status_log` grows only when actuator state changes, so it grows more slowly.
`scripts/cleanup_status_log.py` keeps 14 days by default.

## Simulation And Testing

`tools/simulation_harness.py` creates a throwaway MariaDB database, imports the
runtime scripts, monkeypatches GPIO and time, and runs deterministic control
scenarios. It does not move real relays.

The harness currently exercises:

- day/night temperature cycles
- solar heating cycles
- cloud-flicker threshold hover
- cold-night heater stress
- dynamic hysteresis widening
- stale and partial sensor failure
- SQL override behavior
- MariaDB outage behavior
- systemd-style `SIGTERM` shutdown
- startup GPIO state
- damaged/missing singleton tables
- strict SQL mode
- DS18B20 sentinel values
- alert cooldown behavior

The harness needs admin database permissions because it creates and drops a
throwaway test database. Set the password with:

```bash
export GREENHOUSE_TEST_DB_ROOT_PASSWORD='your-root-password'
python3 tools/simulation_harness.py
```

## Deployment Notes

The default runtime path used by scripts is:

```text
/home/pi/Greenhouse_Controller/
```

The expected config path is:

```text
/home/pi/Greenhouse_Controller/greenhouse.conf
```

The sample systemd service expects the repository to be checked out or copied to
that location.
