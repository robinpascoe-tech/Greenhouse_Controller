# Greenhouse Controller

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

A Raspberry Pi greenhouse automation project for reading DS18B20 temperature
sensors, storing greenhouse state in MariaDB, and controlling heater,
ventilation fans, circulation fan, and motorized windows through GPIO relays.

This repository is both a working controller and a reference design. It is
intended to be understandable, hackable, and useful to people building their own
greenhouse automation systems.

## What It Does

- Reads multiple DS18B20 1-Wire temperature sensors.
- Stores latest clean readings in MariaDB.
- Records raw sensor diagnostics, including failed reads.
- Controls heater, ventilation fans, circulation fan, and windows.
- Uses SQL-driven day schedules for temperature thresholds.
- Supports temporary fan and window overrides.
- Adds short-cycle protection and dynamic hysteresis widening.
- Detects stale sensors and fails safe.
- Scores sensor health and detects degradation/failure patterns.
- Provides a simulation harness for testing controller behavior without moving
  real relays.

## Safety First

This project controls physical outputs. Review the GPIO assignments, relay
wiring, actuator wiring, and fail-safe behavior before running the controller on
real hardware.

The controller is designed to fail safe where possible:

- GPIO outputs initialize LOW.
- Windows are forced closed at startup.
- Stale/missing inside temperature data triggers emergency shutdown.
- `SIGTERM` and `CTRL+C` route through safe shutdown.
- Heater and fans are turned off during emergency shutdown.
- Windows are closed during emergency shutdown.

You are still responsible for validating the electrical and mechanical behavior
of your own system.

## Hardware Assumptions

The current configuration assumes:

- Raspberry Pi running Raspberry Pi OS Trixie.
- MariaDB running locally on the Pi.
- DS18B20 temperature sensors on the Pi 1-Wire bus.
- Relay outputs connected to Raspberry Pi GPIO.
- Actuators for:
  - heater
  - ventilation fan
  - auxiliary ventilation fan
  - circulation fan
  - rear window motor
  - roof window motor

Sensor IDs and GPIO pins are specific to the original installation. Update them
before deploying to different hardware.

## Software Stack

- Python 3
- MariaDB
- PyMySQL
- `python3-rpi-lgpio` for RPi.GPIO-compatible GPIO access on Raspberry Pi OS
  Trixie
- systemd for running the main controller service
- cron or systemd timers for periodic sensor/maintenance scripts

See [docs/INSTALL.md](docs/INSTALL.md) for full installation instructions.

## Repository Layout

```text
scripts/
  greenhouse_controller.py   Main long-running GPIO controller.
  read_sensors.py            DS18B20 reader and currenttemp updater.
  sensor_health.py           Sensor diagnostics and health scoring.
  cleanup_status_log.py      status_log retention cleanup.
  cleanup_sensor_diagnostics.py
                              sensor_diagnostics retention cleanup.

tools/
  simulation_harness.py      Deterministic controller simulation suite.
  simulate_sensors.py        Fake currenttemp writer for development.
  gpio_monitor.py            Read-only GPIO terminal monitor.

sql/
  schema.sql                 Fresh database schema.
  migrate_schema.sql         Migration for older greenhouse databases.

config/
  greenhouse.conf.example    Runtime configuration template.
  greenhouse-controller.service.example
                              Example systemd service file.

docs/
  INSTALL.md                 Installation guide.
  ENGINEERING_OVERVIEW.md    System architecture and behavior notes.

html/
  Legacy PHP dashboard files.

archive/
  Historical notes and original Python 2 material.
```

## Main Runtime Scripts

`scripts/greenhouse_controller.py`
: Long-running process that reads SQL state and controls GPIO outputs.

`scripts/read_sensors.py`
: Reads DS18B20 sensors, writes clean values to `currenttemp`, and writes every
  attempt to `sensor_diagnostics`.

`scripts/sensor_health.py`
: Analyzes diagnostic history for CRC instability, flatlines, sentinel values,
  noise, drift, degradation, and failure.

`scripts/cleanup_status_log.py`
: Deletes old actuator history rows to keep the database from growing forever.

`scripts/cleanup_sensor_diagnostics.py`
: Deletes old raw sensor diagnostic rows. This table grows quickly because every
  sensor read attempt is recorded.

## Database

The database is the shared state layer between scripts and dashboards.

Important tables include:

- `currenttemp`
- `settings`
- `overrides`
- `status`
- `status_log`
- `sensor_diagnostics`
- `sensor_health`
- `sensor_state`
- `sensor_alerts`
- `sensor_profile`

Fresh installs use [sql/schema.sql](sql/schema.sql). Existing legacy installs
can review and use [sql/migrate_schema.sql](sql/migrate_schema.sql).

## Quick Start

On a Raspberry Pi:

```bash
sudo apt update
sudo apt install git
cd /home/pi
git clone https://github.com/robinpascoe-tech/Greenhouse_Controller.git Greenhouse_Controller
cd /home/pi/Greenhouse_Controller
xargs -a apt-packages.txt sudo apt install -y
```

Then follow the full guide:

- [Installation Guide](docs/INSTALL.md)
- [Engineering Overview](docs/ENGINEERING_OVERVIEW.md)

## Configuration

Copy the example config:

```bash
cp config/greenhouse.conf.example greenhouse.conf
chmod 600 greenhouse.conf
```

Update the database password before running the scripts.

The default runtime config path is:

```text
/home/pi/Greenhouse_Controller/greenhouse.conf
```

## Running As A Service

An example systemd unit is provided:

```text
config/greenhouse-controller.service.example
```

Typical install:

```bash
sudo cp config/greenhouse-controller.service.example \
  /etc/systemd/system/greenhouse-controller.service
sudo systemctl daemon-reload
sudo systemctl enable --now greenhouse-controller
```

View logs:

```bash
journalctl -u greenhouse-controller -f
```

## Testing And Simulation

The simulation harness creates a throwaway MariaDB database, monkeypatches GPIO
and time, and verifies controller behavior without moving real relays.

```bash
export GREENHOUSE_TEST_DB_ROOT_PASSWORD='your-root-password'
python3 tools/simulation_harness.py
```

The harness covers scenarios such as:

- normal day/night temperature cycles
- cloud-flicker threshold hover
- cold-night heater stress
- dynamic hysteresis widening
- stale and partial sensor failure
- override expiration
- MariaDB outage
- systemd-style shutdown
- strict SQL mode
- DS18B20 sentinel values
- alert cooldown behavior

## Legacy Dashboard

The `html/` directory contains legacy PHP dashboard files from the original
project. They are included as historical and practical reference material, but
the modern Python controller does not depend on them.

Review and update credentials, paths, and PHP dependencies before using those
files on a public or production system.

## Known Limitations

- Real-world greenhouse soak testing is still in progress. Treat the current
  release as a release candidate until it has run through several days of live
  weather and actuator behavior.
- Sensor IDs, GPIO pins, relay behavior, motor timing, and SQL schedules are
  installation-specific and must be reviewed before use on different hardware.
- The simulation harness verifies controller logic, but it cannot prove relay
  wiring, actuator direction, mechanical limits, or thermal behavior in a real
  greenhouse.
- The legacy dashboard is included for reference and has not yet been modernized
  to the same standard as the Python controller.
- Wiring diagrams and deployment examples are planned but not included yet.

## Contributing

Contributions, ideas, and adaptations are welcome.

By contributing to this repository, you agree that your contribution is provided
under the same license as the project: GPL-3.0-or-later. See
[CONTRIBUTING.md](CONTRIBUTING.md) for contributor guidelines.

Good areas for future improvement include:

- systemd timer examples for sensor and health scripts
- modern dashboard or API
- automated install script
- better sensor discovery/configuration
- support for additional sensor types
- packaged tests that do not require a live MariaDB instance
- documentation for relay wiring and GPIO safety

Before opening a pull request:

- Keep changes focused.
- Avoid committing secrets or live credentials.
- Update docs when paths, tables, or behavior change.
- Run Python syntax checks:

```bash
python3 -m py_compile scripts/*.py tools/*.py
```

If your change affects controller behavior, run the simulation harness when
possible.

## Project Status

This project is being prepared as a `v0.9.0` release candidate for public use
and review. It began as a real greenhouse controller and still contains some
legacy material alongside the newer refactored Python scripts.

Expect to review configuration, GPIO assignments, sensor IDs, and SQL passwords
before using it in your own greenhouse.

## License

This project is licensed under the GNU General Public License v3.0 or later.
See [LICENSE](LICENSE) for the full license text.
