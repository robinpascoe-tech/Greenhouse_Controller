# Greenhouse Soak Test Protocol

This protocol describes how to run and collect evidence from a multi-day
greenhouse controller soak test. The goal is to compare real greenhouse
operation against expected controller behavior before promoting a release or
validating a development branch.

## Recommended Test Order

For release validation, run the real greenhouse soak test from latest `main`.
This keeps the field test focused on the stable branch while including the
timestamp, override, dashboard, default-schedule, sensor freshness, and
sensor-health fixes that were validated for `v1.0.0`.

After the stable baseline is understood, run a separate soak test from
`develop` to evaluate newer behavior such as outside-temperature-aware cooling
and expanded sensor diagnostics.

Suggested sequence:

1. Soak test latest `main` for several days.
2. Analyze logs, SQL history, and field notes.
3. Fix any release issues or promote/tag the stable release.
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

## Deployment Readiness Checklist

Before starting a soak test, verify the Pi is running the branch and commit you
intend to test.

For a `develop` soak test:

```bash
cd /home/pi/Greenhouse_Controller
git fetch --all --tags
git switch develop
git pull --ff-only
python3 -m py_compile scripts/*.py tools/*.py
```

If the controller code has changed, restart the service only after the code,
config, database schema, and cron entries are confirmed:

```bash
systemctl status greenhouse-controller.service --no-pager
crontab -l
```

Verify expected runtime state:

```bash
git status --short --branch
git describe --tags --always --dirty
systemctl show greenhouse-controller.service \
  --property=ActiveState,SubState,MainPID,NRestarts,ExecMainStartTimestamp
tail -n 80 /home/pi/Greenhouse_Controller/thermostat.log
tail -n 80 /home/pi/Greenhouse_Controller/greenhouse_sensors.log
```

Record in `notes.md`:

- branch/tag under test
- full commit hash
- start time
- weather expectations
- whether woodstove use is expected
- whether any manual overrides or maintenance are planned

Do not run `tools/gpio_integration_test.py` against a live connected
greenhouse unless it is explicitly safe for the real relays to move.

## Version And Preflight Checks

Record the exact code version:

```bash
cd /home/pi/Greenhouse_Controller
git status --short --branch
git rev-parse HEAD
git describe --tags --always
```

For a stable-branch soak:

```bash
git fetch --all --tags
git switch main
git pull --ff-only
```

For a development soak:

```bash
git fetch --all --tags
git switch develop
git pull --ff-only
```

To reproduce a tagged release exactly, check out that tag instead of latest
`main`.

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
export GREENHOUSE_TEST_DB_ROOT_PASSWORD='your-root-password'
python3 tools/simulation_harness.py
```

The simulation harness records GPIO calls instead of moving real relays.

For guarded Raspberry Pi GPIO validation on `develop`, only when safe:

```bash
export GREENHOUSE_ALLOW_REAL_GPIO_TEST=1
export GREENHOUSE_TEST_DB_ROOT_PASSWORD='your-root-password'
python3 tools/gpio_integration_test.py
```

The GPIO integration test drives real GPIO pins. Do not run it unless it is
safe for the configured GPIO pins to energize.

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

The preferred collection method is the repository helper:

```bash
cd /home/pi/Greenhouse_Controller
python3 tools/collect_soak_data.py --since "2026-06-07 15:00:00"
```

The helper prints the generated archive path, such as:

```bash
/tmp/greenhouse_soak_20260610T171823Z.tar.gz
```

It collects notes, logs, service state, Git metadata, SQL schema files, a
database snapshot, and a MariaDB dump. Database credentials are read from
`greenhouse.conf` and are not printed.

Use `--output-root /path/to/dir` if you want the archive somewhere other than
`/tmp`. Use `--keep-unpacked` if you want to inspect the collection directory
on the Pi before copying it elsewhere.

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
- recent-but-stale grace events
- fallback from `AverageInsideTemp` to `FrontTemp` or `BackTemp`
- stale or missing `OutsideTemp`
- DS18B20 sentinel values such as `85.0 C` or `-127.0 C`
- CRC instability
- persistent CRC instability over 6-hour and 24-hour windows
- flatline readings
- noisy or drifting sensors
- sensor-health alerts and cooldown behavior
- environmental trend notes that prevent normal greenhouse ramps from being
  marked as degradation
- peer outlier detection if three or more comparable inside-air sensors exist

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

This does not apply to stable releases unless the adaptive cooling work has
been merged into the tested branch.

## Warning Signs

Investigate before promoting a release if any of these appear:

- actuator state in SQL disagrees with observed real hardware
- heater runs but temperature continues falling for a long period
- fans/windows cause large overcooling events
- repeated dynamic hysteresis warnings
- repeated sensor fallback or recent-but-stale grace warnings
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
- recommendation: keep testing, patch the branch, or promote/tag the release
