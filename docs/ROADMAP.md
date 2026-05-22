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

## 4. Expanded Alerting

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

## 5. Forecast-Aware Control

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

## 6. Dashboard Modernization

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

## 7. Simulation And Test Expansion

Keep growing the simulation harness as smarter behavior is added.

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
6. Add expanded trend-based alerting.
7. Add forecast ingestion and forecast-aware decisions.
8. Build a modern dashboard around the improved state model.

