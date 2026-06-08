# Development Roadmap

This roadmap captures high-value directions for the project after the `v0.9.0`
release candidate. It is intended as a living planning document, not a promise
that every feature will land in this exact order.

The overall theme is to move from a schedule-driven thermostat toward a more
adaptive greenhouse controller that understands outdoor conditions, thermal
trends, hardware limits, and operational risk.

## 1. Adaptive Ventilation Logic

Use outside temperature and recent temperature trends to choose cooling actions
more intelligently.

Status: initial outside-temperature-aware fan/window selection is implemented
on `develop`. Further work can refine thresholds after real greenhouse testing
and add trend/rate-of-change inputs.

Initial rule-based behavior could include:

- If the greenhouse is overheating while outside air is very cold, prefer
  ventilation fans before opening windows. This should reduce heat loss and
  lower the chance of overcooling.
- If outside air is moderately cooler than inside air, prefer windows for
  gentler convective cooling.
- If outside air is close to or warmer than inside air, recognize that windows
  may have limited cooling value.
- If the greenhouse cools too quickly after fans or windows activate, close or
  stop earlier and widen hysteresis to reduce cycling.
- If the greenhouse heats back up too quickly after cooling stops, widen
  hysteresis or lengthen minimum rest times before the next cooling action.

This should be developed with simulation scenarios before relying on it in the
greenhouse.

## 2. Controller Decision Refactor

Separate the controller's decision-making into clearer layers before adding too
much smarter behavior.

Useful layers:

- read current SQL and sensor state
- calculate inside/outside temperature trends
- choose heating action
- choose cooling action
- apply manual overrides
- apply short-cycle protection and hysteresis rules
- apply safety rules
- write GPIO and status state

This makes the controller easier to understand, test, and extend.

## 3. Sensor Assignment And Discovery

Move DS18B20 sensor IDs out of Python code and into configuration or SQL.

A future interactive tool could guide setup:

```bash
python3 tools/assign_sensors.py
```

Possible workflow:

1. List all detected DS18B20 sensors.
2. Ask the user to warm a specific sensor location, such as front, back, outside,
   or woodstove.
3. Watch all detected sensors for the strongest positive temperature slope.
4. Confirm the detected sensor with the user.
5. Save the mapping to config or SQL.
6. Have `read_sensors.py` load the mapping instead of using hardcoded IDs.

This would make the project much easier for other people to install on their
own hardware.

## 4. DS18B20 Qualification And Calibration

Create a script and bench-test protocol for screening inexpensive DS18B20
sensors before they are installed in hard-to-reach greenhouse locations.

Motivation:

- DS18B20 sensors are inexpensive in bulk, but batches can include defective,
  poorly calibrated, noisy, slow, or intermittently failing sensors.
- Temperature sensors are central to safe greenhouse control, so bad sensors
  should be found before installation.
- Replacing installed sensors can be time consuming, especially once wiring is
  routed, sealed, or mounted in plant areas.

Proposed tool:

```bash
python3 tools/qualify_ds18b20_sensors.py
```

Possible workflow:

1. Connect several DS18B20 sensors to the Raspberry Pi on the same 1-Wire bus.
2. Sample every 30-60 seconds for 12-24 hours at stable ambient temperature.
3. Store raw readings by sensor ID in a CSV or SQL qualification table.
4. Compare each sensor against the group median at each timestamp.
5. Flag sensors with persistent offset, excessive noise, dropouts, CRC/read
   failures, unrealistic jumps, or slow response.
6. Rank sensors so the best units can be selected for the most important
   greenhouse locations.
7. Optionally generate a calibration report with recommended offset values.

Recommended batch size:

- Minimum useful batch: 5 sensors. This is enough to spot obvious outliers by
  comparing each sensor to the group median.
- Better practical batch: 8-12 sensors. This gives a stronger majority signal,
  makes one or two bad sensors easier to identify, and is still manageable on a
  breadboard or temporary wiring harness.
- Best confidence: 15 or more sensors, especially when qualifying a large bulk
  purchase. At that point, the median and interquartile spread become more
  trustworthy, but wiring and labeling discipline matter more.

A practical target for this project is 8-12 sensors per qualification run. If
only 5 sensors are tested, use the results mainly to reject clear failures, not
to create high-confidence calibration offsets.

Extended calibration protocol:

1. Place all waterproof sensor tips in a stirred ice-water bath and allow them
   to stabilize.
2. Record stabilized readings long enough to calculate median, noise, and
   sensor-to-sensor spread.
3. Move sensors to ambient air or a stirred room-temperature water bath and
   allow them to stabilize again.
4. Optionally place sensors in a boiling-water bath and allow them to stabilize,
   adjusting the expected boiling point for altitude and local pressure if using
   it as an absolute reference.
5. Compare each sensor's readings against the group median at each plateau.
6. For sensors that track the group consistently with a nearly constant offset,
   calculate a simple offset correction.
7. For sensors whose error changes significantly across the temperature range,
   mark them as lower quality or consider a two-point linear correction only if
   the added complexity is justified.

Design notes:

- The group median is a good implied reference when most sensors agree, but it
  is not a true calibration standard.
- A known-good reference thermometer would make the protocol much stronger,
  especially at ice-water and ambient points.
- Stirred water baths are better than still air for comparing sensors because
  all probes experience nearly the same temperature.
- Boiling-water testing may be unnecessary for greenhouse use because the
  normal operating range is far lower; ice-water and ambient/greenhouse-range
  testing may be more relevant.
- Qualification should consider stability and failure behavior, not only static
  offset. A slightly offset but stable sensor can be corrected; a noisy or
  intermittent sensor should be rejected.

Possible report fields:

- sensor ID
- sample count
- missing/read-failure count
- median offset from group median
- maximum absolute deviation
- standard deviation or median absolute deviation
- response lag during temperature transitions
- recommended use: primary, secondary, noncritical, reject
- recommended calibration offset, if appropriate

## 5. Expanded Alerting

Add more operational alerts, especially alerts based on trends rather than only
absolute thresholds.

Useful alert types:

- freezing risk: inside temperature near low threshold and still falling
- heater ineffective: heater active but temperature continues to drop
- woodstove or solar overheating: temperature rising quickly despite cooling
- cooling ineffective: fans/windows active but temperature is not dropping
- sensor stale or partially failed
- outside frost risk
- actuator response suspicious, such as commanded cooling with no plausible
  temperature response
- manual intervention suggested, such as watering plants during fast heat rise

Alerts should keep cooldowns and severity levels so they remain useful instead
of noisy.

## 6. Sensor Health And Soak Analysis Tools

The second greenhouse soak test showed that health scoring needs to distinguish
temperature plausibility from reliability. A sensor can track temperature well
while still having persistent CRC errors that deserve attention.

High-value follow-up tools:

- 1-Wire bus health report: summarize CRC rates by sensor over 1h, 6h, 24h,
  and full soak-test windows.
- Installed wiring diagnostics: flag sensors whose CRC rate is much worse than
  the rest of the bus and suggest checks such as connector quality, cable
  routing, moisture intrusion, pull-up resistance, splice quality, and sensor
  replacement.
- Role-specific sensor health scoring: tune outdoor, system, equipment, and
  derived sensors differently from inside-air peer sensors.
- Soak-test report generator: turn database dumps, logs, replay outputs, and
  notes into a repeatable summary of actuator events, sensor reliability,
  stale gaps, CRC history, temperature response, and unexpected behavior.
- Maintenance and annotation logging: provide a simple table or CLI for marking
  events such as door open, Pi backup, sensor replacement, watering, manual
  work, or power/network maintenance.

This work should build on `tools/replay_sensor_health_history.py`, which can
re-run `sensor_health.py` against historical diagnostic data with realistic
rolling time windows.

## 7. Pi Reliability And Self-Recovery

Add Raspberry Pi platform reliability features so the controller can recover
from common unattended-field failures.

Controller startup sensor wait:

- On controller startup, if inside temperature rows are missing or stale, wait
  briefly for `read_sensors.py` to populate fresh readings before entering the
  normal control loop.
- Keep this startup wait bounded, for example 60-90 seconds, so a real sensor
  reader failure still triggers fail-safe shutdown.
- Log the wait clearly so soak-test analysis can distinguish expected startup
  synchronization from runtime stale-sensor problems.
- Do not weaken normal runtime stale-sensor safety behavior. Once the
  controller has started successfully, missing or stale inside readings should
  still lead to the existing recent-reading grace path and then emergency
  shutdown.
- Consider making the startup wait configurable in `greenhouse.conf` for
  installations with different cron/timer schedules.

Watchdog integration:

- Enable and document the Raspberry Pi/Linux hardware watchdog.
- Add a lightweight heartbeat that only feeds the watchdog when critical
  services are healthy.
- Decide which conditions should stop feeding the watchdog and allow a reboot,
  such as controller lockup, repeated failed safe-shutdown attempts, or severe
  system instability.
- Make sure watchdog behavior does not fight normal service restarts or
  intentional maintenance.

Wireless health and repair:

- Create a script that checks Wi-Fi interface state, IP address, default route,
  DNS resolution, and reachability of expected local/network targets.
- Attempt gentle recovery first, such as restarting networking components or
  cycling the wireless interface.
- Escalate only after repeated failures, possibly by coordinating with the
  watchdog or intentionally rebooting the Pi.
- Log repair attempts to a file and/or SQL table so connectivity issues can be
  reviewed after a soak test.

This should be designed carefully: greenhouse control must remain safe even
when network repair is running, and wireless repair should not interrupt the
controller unless a reboot is truly warranted.

## 8. Forecast-Aware Control

Use an online weather forecast to make earlier, more efficient control decisions.

Possible behaviors:

- On a hot sunny day, cool the greenhouse more aggressively in the morning so it
  can absorb solar heating later.
- Before a very cold night, allow more evening warmth or start heating earlier
  to increase thermal buffer.
- Send early frost warnings based on forecast lows.
- Avoid opening vulnerable windows if rain or high wind is forecast.
- Reduce aggressive morning cooling when the day is expected to be cloudy.

Forecast-aware control should fail gracefully when the internet, API, or
forecast data is unavailable.

## 9. Dashboard Modernization

Replace or supplement the legacy PHP dashboard with a modern interface.

See `docs/DASHBOARD_PLANNING.md` for architecture options and tradeoffs.

High-value dashboard views:

- current temperatures and recent trends
- actuator states
- current schedule period and active thresholds
- manual overrides with expiration times
- sensor health and recent diagnostic failures
- active alerts and alert history
- status log graphs
- configuration review pages
- simulation or test-status summary

Dashboard work should follow the controller state model rather than duplicating
control logic.

## 10. Simulation And Test Expansion

Keep growing the simulation harness as smarter behavior is added.

Status: a guarded GPIO integration test is available as
`tools/gpio_integration_test.py`. It drives real Raspberry Pi GPIO outputs,
samples pin state with `pinctrl`, uses a throwaway database, and should be run
only when it is safe for GPIO pins to energize.

Important future scenarios:

- woodstove overheating while outside air is very cold
- outside air only slightly cooler than inside air
- rapid solar gain after sunrise
- fast cooling after sunset
- cold snap with heater running
- stuck-high, stuck-low, drifting, noisy, and stale sensors
- heater ineffective while temperature trends down
- cooling ineffective while temperature trends up
- cooling-effectiveness metrics after fan/window operation, including drop
  rate, overcooling, and rebound
- cold-weather soak or simulation coverage that exercises real heater behavior
- override conflicts with safety shutdown
- forecast unavailable or clearly stale
- database outage during active heating or cooling

The simulation harness should remain the confidence engine for behavior changes.

## Suggested Development Order

1. Refactor controller decision logic into testable functions.
2. Add outside-temperature-aware cooling choice: fans, windows, both, or wait.
3. Expand simulation coverage for adaptive cooling and woodstove overheating.
4. Move sensor ID mapping out of code and into config or SQL.
5. Build an interactive sensor assignment tool.
6. Build a DS18B20 qualification and calibration tool.
7. Add 1-Wire bus health and role-specific sensor-health reporting.
8. Add soak-test report generation and maintenance annotations.
9. Add Pi watchdog and wireless self-recovery support.
10. Add expanded trend-based alerting.
11. Add forecast ingestion and forecast-aware decisions.
12. Build a modern dashboard around the improved state model.
