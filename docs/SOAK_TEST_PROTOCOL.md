# Greenhouse Soak Test Protocol

This protocol describes how to run and collect evidence from a multi-day
greenhouse controller soak test. The goal is to compare real greenhouse
operation against expected controller behavior before promoting a release
candidate.

## Recommended Test Order

Run the first real greenhouse soak test from `main` at the `v0.9.0` tag. This
keeps the first field test focused on the stable release candidate.

After the baseline is understood, run a separate soak test from `develop` to
evaluate newer behavior such as outside-temperature-aware cooling.

Suggested sequence:

1. Soak test `main` / `v0.9.0` for several days.
2. Analyze logs, SQL history, and field notes.
3. Fix any release-candidate issues or promote a stable release.
4. Soak test `develop` as the next smarter-controller candidate.

## Test Duration

Aim for at least 2 to 4 days of continuous operation. More time is better if
weather changes meaningfully during the test.

Useful conditions to capture:

- sunny daytime heating
- cloudy or variable sun
- cold nighttime cooling
- woodstove use, if available
- at least one ventilation/fan/window event
- at least one heater event, if weather permits
- normal sensor-reader and sensor-health runs

## Before Starting

Record the exact code version:

```bash
cd /home/pi/Greenhouse_Controller
git status --short --branch
git rev-parse HEAD
git describe --tags --always
```

For a `v0.9.0` baseline soak:

```bash
git fetch --all --tags
git switch main
git pull --ff-only
git checkout v0.9.0
```

Check service status and recent logs:

```bash
systemctl status greenhouse-controller --no-pager
journalctl -u greenhouse-controller -n 100 --no-pager
```

Run quick syntax checks:

```bash
python3 -m py_compile scripts/*.py tools/*.py
```

Optional bench checks before connecting to the greenhouse:

```bash
export GREENHOUSE_ALLOW_REAL_GPIO_TEST=1
export GREENHOUSE_TEST_DB_ROOT_PASSWORD='your-root-password'
python3 tools/gpio_integration_test.py
```

Only run the GPIO integration test when it is safe for the configured GPIO pins
to energize.

## During The Test

Keep a simple notes file. Human observations are very useful when interpreting
logs.

Suggested `notes.md`:

```text
Soak test branch/tag:
Commit:
Started:
Ended:

Weather notes:
Woodstove used:
Manual overrides:
Watering or manual cooling:
Greenhouse doors opened manually:
Power/network interruptions:
Unexpected actuator behavior:
Anything surprising:
```

When something notable happens, record the approximate time and what you saw.
Examples:

- "13:40 windows open, fans off, sunny, inside felt hot"
- "22:15 woodstove lit"
- "02:30 heater running, outside below freezing"
- "manual fan override enabled for 20 minutes"

## Data To Collect

Create a collection directory after the soak test:

```bash
STAMP=$(date +%Y%m%d-%H%M%S)
OUT=/home/pi/greenhouse_soak_test_$STAMP
mkdir -p "$OUT"
```

Collect Git/version information:

```bash
cd /home/pi/Greenhouse_Controller
{
  git status --short --branch
  git rev-parse HEAD
  git describe --tags --always
  git log --oneline -5
} > "$OUT/git_version.txt"
```

Collect controller logs:

```bash
cp /home/pi/Greenhouse_Controller/thermostat.log "$OUT/" 2>/dev/null || true
journalctl -u greenhouse-controller --since "4 days ago" \
  > "$OUT/systemd_journal_greenhouse-controller.log"
```

Collect database export:

```bash
mysqldump greenhouse \
  currenttemp \
  status \
  status_log \
  settings \
  overrides \
  sensor_diagnostics \
  sensor_health \
  sensor_alerts \
  sensor_state \
  sensor_profile \
  > "$OUT/database_soak_tables.sql"
```

If using a non-root SQL user, add the usual `-u user -p` options.

Copy your notes into the same directory:

```bash
cp notes.md "$OUT/" 2>/dev/null || true
```

Create a compressed archive:

```bash
tar -czf "$OUT.tar.gz" -C "$(dirname "$OUT")" "$(basename "$OUT")"
echo "$OUT.tar.gz"
```

## Analysis Checklist

The soak-test analysis should compare controller intent, SQL state, logs, and
real greenhouse behavior.

### Actuator Behavior

Check whether actuator state changes match the configured thresholds:

- heater ON/OFF around `lowtemp +/- lowtemprange / 2`
- fans ON/OFF around `hightemp +/- hightemprange / 2`
- windows OPEN/CLOSE around `windowtemp +/- windowtemprange / 2`
- circulation fan following the active schedule row
- manual overrides taking effect and expiring correctly

Review `status_log` timing against `thermostat.log` messages.

### Cycling And Hysteresis

Look for excessive switching:

- heater short cycling
- ventilation fan short cycling
- window open/close cycling
- dynamic hysteresis warning messages
- cases where widened hysteresis reduced cycle rate

Measure time between actuator transitions and compare it with the configured
minimum on/off durations.

### Temperature Response

Evaluate greenhouse thermal behavior after actuator changes:

- Does the heater raise temperature as expected?
- Does temperature continue falling while the heater is on?
- Do fans cool the greenhouse too quickly or too slowly?
- Do windows cause overshoot during cold outside conditions?
- Does temperature rebound quickly after fans/windows turn off?
- Are there long periods where the greenhouse remains too hot or too cold?

### Sensors

Review sensor reliability:

- stale inside sensor readings
- fallback from `AverageInsideTemp` to `FrontTemp` or `BackTemp`
- stale or missing `OutsideTemp`
- DS18B20 sentinel values such as `85.0 C` or `-127.0 C`
- CRC instability
- persistent CRC instability over 6-hour and 24-hour windows
- flatline readings
- noisy or drifting sensors
- sensor-health alerts and cooldown behavior

### Safety And Failure Handling

Confirm no unexpected safety events occurred:

- emergency shutdown
- MariaDB retry storms
- GPIO cleanup
- window close on shutdown
- controller restarts
- service crashes
- missing singleton rows repaired at startup

If safety events did occur, determine whether they were appropriate.

### Outside-Aware Cooling

For `develop` soak tests, also review adaptive cooling:

- cold outside and greenhouse overheating: fans preferred before windows
- outside near inside temperature: windows preferred for gentler cooling
- outside warmer than inside: windows avoided
- urgent overheating: fans and windows both used
- stale outside temperature: fallback to legacy cooling

This does not apply to the `v0.9.0` baseline unless the adaptive cooling work
has been merged into the tested branch.

## Warning Signs

Investigate before promoting a release if any of these appear:

- actuator state in SQL disagrees with observed real hardware
- heater runs but temperature continues falling for a long period
- fans/windows cause large overcooling events
- repeated dynamic hysteresis warnings
- repeated sensor fallback or stale sensor warnings
- emergency shutdown during normal conditions
- MariaDB connection failures outside deliberate testing
- windows fail to close at shutdown
- status_log shows rapid cycling not explained by thresholds or overrides
- manual overrides do not expire

## Expected Report

The analysis report should include:

- test period and code version
- summary of weather and manual actions
- actuator event timeline
- temperature and sensor summary
- any safety or failure events
- behavior that matched expectations
- behavior that did not match expectations
- tuning recommendations
- bug fixes or follow-up tests
- recommendation: keep testing, patch release candidate, or promote toward
  `v1.0.0`

