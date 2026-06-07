# Agent Briefing

This file gives future coding-agent sessions quick project context. Read it
before making changes, then inspect the relevant code and docs.

## Project Summary

Greenhouse Controller is a Raspberry Pi greenhouse automation project. It reads
DS18B20 temperature sensors, stores state in MariaDB, and controls heater,
ventilation fans, circulation fan, and motorized windows through GPIO relays.

This project controls physical hardware. Treat safety behavior as part of the
core product, not as incidental implementation detail.

## Branches And Release State

- `main` is the stable release branch.
- `develop` is the active development branch for new controller behavior.
- `v1.0.0` is the first field-tested stable release.
- `v0.9.1` and `v0.9.0` are older release-candidate tags kept for comparison.
- Smarter controller work, including outside-aware cooling and expanded sensor
  diagnostics, lives on `develop` unless merged later.

Do not move existing release tags unless explicitly asked.

## Important Docs

- `README.md`: project overview and quick start.
- `docs/INSTALL.md`: Raspberry Pi and MariaDB installation.
- `docs/ENGINEERING_OVERVIEW.md`: system architecture and control behavior.
- `docs/SOAK_TEST_PROTOCOL.md`: field-test collection and analysis protocol.
- `CONTRIBUTING.md`: contribution and license expectations.

`docs/ROADMAP.md` currently lives on `develop`; check that branch before
starting new feature work.

## Runtime Files

- `scripts/greenhouse_controller.py`: long-running GPIO controller.
- `scripts/read_sensors.py`: DS18B20 reader and `currenttemp` updater.
- `scripts/sensor_health.py`: sensor diagnostics and health scoring.
- `scripts/cleanup_status_log.py`: actuator log retention cleanup.
- `scripts/cleanup_sensor_diagnostics.py`: raw sensor diagnostic retention
  cleanup.
- `tools/simulation_harness.py`: deterministic simulation suite using a
  throwaway MariaDB database and fake GPIO.
- `tools/gpio_monitor.py`: read-only GPIO state monitor.
- `sql/schema.sql`: fresh database schema.
- `sql/migrate_schema.sql`: legacy database migration script.

## Safety Rules

Preserve these controller behaviors unless the user explicitly chooses a
different safety design:

- GPIO outputs initialize LOW.
- Unused GPIO outputs are forced LOW.
- Windows are forced closed at startup.
- Emergency shutdown turns heater/fans off, closes windows, calls GPIO cleanup,
  and exits.
- `SIGTERM` and `KeyboardInterrupt` route through safe shutdown.
- Missing or stale inside temperature data triggers emergency shutdown after
  one recent-reading grace controller loop.
- Startup repairs missing singleton `status` and `overrides` rows.
- Manual fan/window overrides bypass short-cycle protection but still record
  actuator movement.
- Forced startup/shutdown window movement should not poison normal cycle
  history.

Be careful with physical output order and relay timing. Window open/close
sequences are intentionally explicit.

## Testing Expectations

For controller behavior changes:

1. Run Python syntax checks:

   ```bash
   python3 -m py_compile scripts/*.py tools/*.py
   ```

2. Run the simulation harness when MariaDB is available:

   ```bash
   export GREENHOUSE_TEST_DB_ROOT_PASSWORD='your-root-password'
   python3 tools/simulation_harness.py
   ```

The local Windows environment may only have Windows Store Python shims. If local
Python validation fails for that reason, use the Raspberry Pi test environment
when available.

## Raspberry Pi Notes

The project has been tested on Raspberry Pi OS Trixie with MariaDB. Use
`python3-rpi-lgpio` for RPi.GPIO-compatible access on Trixie.

Default runtime paths:

- repository: `/home/pi/Greenhouse_Controller`
- config: `/home/pi/Greenhouse_Controller/greenhouse.conf`
- controller log: `/home/pi/Greenhouse_Controller/thermostat.log`

Prefer native OpenSSH with the `greenhouse-pi` host alias when available. For
multi-command Pi work, copy a script with `scp` and run it with `ssh` instead of
packing complex shell logic into one remote command.

Do not commit `greenhouse.conf`, database passwords, SSH passwords, SQL dumps
with secrets, local bundle backups, or live logs unless the user explicitly
sanitizes and requests it.

## Database Compatibility

The controller expects MariaDB tables including:

- `currenttemp`
- `settings`
- `overrides`
- `status`
- `status_log`
- `sensor_diagnostics`
- `sensor_health`
- `sensor_alerts`
- `sensor_state`
- `sensor_profile`

Schema changes must be reflected in:

- `sql/schema.sql`
- `sql/migrate_schema.sql` when legacy databases need migration
- docs if install or operation changes
- tests/simulations when behavior changes

## Development Preferences

- Keep changes focused and commit coherent checkpoints.
- Prefer existing project patterns over new abstractions.
- For safety-critical changes, update simulation coverage and docs.
- Do not rewrite Git history or force-push unless explicitly requested.
- Do not revert user changes without explicit approval.
- Keep `main` stable; do active work on `develop` unless told otherwise.
