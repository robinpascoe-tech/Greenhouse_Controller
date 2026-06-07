# Release Notes

## v1.0.0

`v1.0.0` is the first field-tested stable release of Greenhouse Controller.
It was promoted after multi-day greenhouse soak testing of the `main` branch.

### Highlights

- Raspberry Pi OS Trixie support with `python3-rpi-lgpio`.
- MariaDB-backed greenhouse state, actuator history, and sensor diagnostics.
- Long-running systemd controller for heater, ventilation fans, circulation
  fan, and motorized windows.
- Cron-friendly DS18B20 sensor reader.
- Sensor health scoring with peer/environment context.
- Short-cycle protection with dynamic hysteresis widening.
- Manual fan/window overrides with expiration.
- Safe shutdown handling for `SIGTERM` and `CTRL+C`.
- Recent-reading grace cycle for delayed sensor updates before fail-safe
  shutdown.
- Legacy PHP dashboard and dashboard deployment helper.
- Simulation harness for controller behavior testing.

### Field-Tested Behavior

The v1 soak test confirmed:

- safe shutdown during planned stop/backup activity
- clean controller recovery after startup
- expected circulation fan schedule behavior
- sensible window and ventilation fan response to greenhouse heating
- no concerning heater, fan, or window short-cycling pattern
- continued database logging and dashboard compatibility

### Known Notes

- Sensor IDs, GPIO pins, relay behavior, motor timing, and SQL schedules are
  installation-specific and must be reviewed before running on new hardware.
- DS18B20 sensor quality varies. Use diagnostic history and physical
  validation to identify marginal sensors.
- Raspberry Pi undervoltage warnings should be fixed at the hardware/power
  level before relying on unattended long-term control.
- The dashboard is functional legacy PHP and is planned for future
  modernization.
- Wiring diagrams and richer deployment examples are still planned.
