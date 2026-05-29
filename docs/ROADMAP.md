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

## 6. Forecast-Aware Control

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

## 7. Dashboard Modernization

Replace or supplement the legacy PHP dashboard with a modern interface.

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

## 8. Simulation And Test Expansion

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
7. Add expanded trend-based alerting.
8. Add forecast ingestion and forecast-aware decisions.
9. Build a modern dashboard around the improved state model.
