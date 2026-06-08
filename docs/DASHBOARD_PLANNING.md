# Dashboard Planning

This document captures planning notes for modernizing the Greenhouse Controller
dashboard while the controller soak testing continues.

The current dashboard is a legacy PHP interface served by nginx from
`/var/www/html`. Cacti also runs under nginx and remains useful for historical
graphs. The modernization goal is not to remove Cacti; it is to build a better
operational dashboard around the controller while keeping Cacti available for
long-term graphing.

## Goals

- Keep the Raspberry Pi lightweight and reliable.
- Preserve nginx and Cacti.
- Avoid disturbing controller soak tests while planning.
- Use responsive design so the dashboard works well on a phone, tablet, or
  computer screen.
- Show live greenhouse state clearly.
- Keep manual controls understandable and safe.
- Make sensor health, actuator history, and alerts easier to interpret.
- Avoid duplicating controller logic in the dashboard.
- Keep secrets out of the repository.

## Useful Dashboard Views

- Current temperatures with freshness/age indicators.
- Current actuator states: heater, ventilation fan, circulation fan, windows.
- Active schedule period and thresholds.
- Manual override controls with expiration time and clear on/off/open/close
  semantics.
- Sensor health summary with CRC, stale, drift, flatline, and failure notes.
- Recent controller events from `status_log`.
- Active alerts and alert history.
- Links or embedded views for Cacti historical temperature/operation graphs.
- Soak-test notes and maintenance annotations.
- Configuration review page for paths, sensor names, GPIO pins, and SQL
  schedule values.

## Display Modes

The primary desktop view should feel closer to a small SCADA display than a
traditional web page. It should be suitable for leaving open on a computer
screen in the greenhouse or nearby work area.

The desktop layout should show the current operating picture at a glance:

- sensor readings with freshness and trend indicators
- actuator status for heater, ventilation fan, circulation fan, and windows
- time each actuator has been in its current state
- recent temperature graph
- current schedule period and active thresholds
- active overrides and expiration times
- scrolling control/event history
- sensor health summary

Modules should update automatically without requiring a manual page refresh.
The dashboard should clearly indicate if live updates stop or data becomes
stale.

Tablet and phone layouts should be responsive, not just scaled-down desktop
views. A phone does not need to show every module at once. The mobile view
should prioritize current temperature, actuator state, active overrides,
freshness warnings, and links to deeper detail pages.

The SCADA-style desktop view should be optimized around common 16:10 and 16:9
monitor aspect ratios, rather than a fixed pixel resolution. It should work on
ordinary 1080p screens as well as higher-resolution displays such as
3840x2400. Layouts should use responsive grid sizing, aspect-ratio-aware
panels, and sensible minimum/maximum widths instead of assuming one exact
monitor size.

## Prototype Scope

The first prototype should be a small read-only Flask app. Schedule changes and
manual overrides can remain in the legacy PHP interface while the new dashboard
proves itself.

The read-only prototype should focus on:

- current state
- recent trends
- current schedule values
- active overrides
- control/event history
- sensor health
- links or selected embeds for Cacti graphs

Manual control writes should be added only after authentication, CSRF
protection, clear confirmation states, and safe override semantics are designed
and tested.

## Architecture Options

### Option 1: Modernized PHP Under nginx

Keep the dashboard as PHP served directly by nginx/php-fpm.

Pros:

- Smallest change from the existing dashboard.
- Fits current nginx/PHP/Cacti setup.
- No extra application server process.
- Low resource usage on the Raspberry Pi.
- Familiar for maintainers with PHP experience.
- Easy to deploy by copying files into `/var/www/html`.
- Cacti can stay exactly where it is.

Cons:

- PHP pages can become tangled if controller logic, SQL access, and display
  logic are not kept separate.
- Harder to build a clean API for future tools.
- Modern interactive UI patterns can be clunky without adding JavaScript.
- Testing is usually weaker unless we deliberately add structure.
- Long-running/background logic should not live in PHP request handlers.

Best fit:

- A practical near-term dashboard refresh.
- Live status pages, forms, and links to Cacti.
- Minimal resource impact and minimal deployment complexity.

Recommended shape if chosen:

- Keep nginx + php-fpm.
- Create shared PHP helpers for database access, formatting, and auth.
- Keep controller decisions out of PHP.
- Use Cacti for long historical graphs.
- Use small PHP endpoints that return JSON for live values if the UI needs
  lightweight polling.

### Option 2: Flask

Run a small Python Flask app behind nginx as a reverse proxy.

Pros:

- Python matches the controller codebase.
- Easy to share parsing, formatting, and database helper patterns.
- Simple to build JSON endpoints and server-rendered pages.
- Lightweight enough for a Raspberry Pi if kept modest.
- Good fit for future tools such as sensor assignment, soak reports, and
  maintenance annotations.
- Easier to test than legacy PHP if the app is structured cleanly.

Cons:

- Adds another service to run and monitor.
- Requires systemd service configuration and nginx reverse proxy config.
- Slightly more resource usage than plain PHP pages.
- Need to avoid importing controller modules in ways that could touch GPIO or
  perform side effects.
- More deployment moving parts than the current dashboard.

Best fit:

- A modern operational dashboard with live JSON/API endpoints.
- Future admin tools that benefit from Python.
- A middle path between old PHP and a larger web stack.

Recommended shape if chosen:

- Serve Flask through gunicorn or waitress behind nginx.
- Keep Cacti under its existing nginx path.
- Keep Flask read-mostly at first.
- Add write endpoints for overrides only after CSRF/auth and clear safety
  checks are in place.
- Keep dashboard database helpers separate from controller GPIO code.

### Option 3: FastAPI

Run a Python FastAPI app behind nginx as a reverse proxy.

Pros:

- Excellent API-first structure.
- Automatic OpenAPI docs for endpoints.
- Good fit if we want a clean backend API for future mobile/web clients.
- Strong request/response typing can reduce mistakes.
- Works well with a separate frontend.

Cons:

- More framework complexity than this project may need right now.
- Typically pushes the project toward API plus frontend architecture.
- Adds another service and Python dependencies.
- Async features are not especially useful if most operations are simple SQL
  queries.
- More to explain for new contributors than PHP or Flask.

Best fit:

- If the dashboard becomes a proper API-backed application.
- If multiple clients are planned, such as web dashboard, mobile view, and
  external automation integrations.

Recommended shape if chosen:

- Keep the API small and explicit.
- Serve via uvicorn behind nginx.
- Keep Cacti separate.
- Build a minimal frontend first; avoid a large JavaScript framework until the
  API proves useful.

### Option 4: Lightweight Static Frontend Plus JSON Endpoints

Serve static HTML/CSS/JavaScript from nginx and fetch data from small PHP,
Flask, or FastAPI JSON endpoints.

Pros:

- nginx serves static files very efficiently.
- UI can feel modern without a heavy server framework.
- Backend endpoints can stay small and focused.
- Easy to poll current state every few seconds.
- Cacti links or image embeds can live beside custom dashboard panels.

Cons:

- Still needs some backend for SQL data and manual override writes.
- JavaScript can become messy without a little structure.
- Build tooling should be avoided or kept minimal on the Pi.
- Security matters for write actions; override forms should not be casual GET
  links.

Best fit:

- A modern dashboard that stays light on Raspberry Pi resources.
- A staged migration where old PHP remains available.

Recommended shape if chosen:

- Use static files with plain JavaScript or a very small library.
- Avoid Node-based build steps at first.
- Use PHP or Flask JSON endpoints.
- Add progressive enhancement: the page should still be understandable if live
  polling fails.

### Option 5: Heavier JavaScript SPA

Use a frontend framework such as React, Vue, or Svelte with a backend API.

Pros:

- Most flexible UI.
- Good component model for complex dashboards.
- Easy to create rich interactions and stateful controls.

Cons:

- More tooling and build complexity.
- Heavier contributor/deployment burden.
- More moving parts on a small Pi, even if the built static files are light.
- Likely more than the project needs for the next dashboard milestone.

Best fit:

- Later, if the dashboard grows into a large application.

Recommended shape if chosen:

- Build elsewhere or during release packaging, not as part of Pi runtime.
- Serve only static built assets on the Pi.
- Keep backend API separate and small.

## Resource Considerations

Lowest runtime overhead:

1. nginx + PHP/php-fpm
2. nginx static frontend + small PHP JSON endpoints
3. nginx static frontend + small Flask app
4. nginx + FastAPI
5. heavier SPA plus API

Most maintainable for future Python-centered project tools:

1. Flask
2. FastAPI
3. static frontend plus Flask/FastAPI endpoints
4. structured PHP
5. legacy-style PHP

Lowest migration risk:

1. Improve current PHP dashboard in place
2. Add static frontend with PHP JSON endpoints
3. Add Flask read-only dashboard behind nginx
4. Add FastAPI plus static frontend
5. Full SPA rewrite

## Cacti Integration

Cacti should remain available under nginx for long-term historical graphs.

Possible integration approaches:

- Link to Cacti pages from the new dashboard.
- Keep existing Cacti graph PHP pages for temperature/operation graph groups.
- Embed selected Cacti graph images or pages on graph-focused dashboard pages
  if the paths are stable.
- Add a "Historical Graphs" section that intentionally hands off to Cacti.

The expected embedded graph pages are:

- temperature graphs
- humidity graphs
- operation/actuator graphs
- combined temperature and operation graphs

The main SCADA-style page should show a recent temperature graph, with a
30-minute window as the starting target. There are two practical ways to do
this:

- generate a lightweight 30-minute graph directly from `temperature_log`
- show a configured Cacti graph image URL for the 30-minute temperature graph

A generated dashboard-native graph is more portable because it does not depend
on Cacti graph IDs or install-specific paths. It is also easier to make
auto-update cleanly with the rest of the dashboard. A Cacti graph image is
better if we want visual consistency with existing historical graphs and want
to avoid building graphing logic in the dashboard.

For the first prototype, the preferred direction is a dashboard-native
30-minute temperature graph for the main SCADA-style page, plus configurable
Cacti image links or wrapper pages for the graph-focused pages. This keeps the
main view portable while still preserving Cacti for historical graphing.

The dashboard-native graph should use a small self-hosted JavaScript charting
library fed by a Flask JSON endpoint. This keeps the Flask app simple, avoids a
server-side image-generation dependency, and lets the browser handle frequent
auto-updates. A lightweight time-series library such as uPlot is a good fit; a
more common library such as Chart.js would also work if contributor familiarity
matters more than minimizing JavaScript size.

Because Cacti graph locations can differ by installation, embedded Cacti graph
URLs should be configurable. They should not be hard-coded into templates.

The custom dashboard should focus on live operations, safety, controls, sensor
health, and interpretation. Cacti should continue doing what it does well:
long-term graphing.

The main dashboard page should not become crowded with every historical graph.
It can show a recent compact temperature graph, while deeper graph pages can
embed selected Cacti views and link to the full Cacti interface.

Direct graph image links, or small wrapper pages using direct graph image
links, are preferred over iframes for embedded dashboard graphs. Iframes are
more likely to bring in Cacti navigation and graph controls that are useful in
Cacti itself but distracting in the operator dashboard.

## Authentication

Local-network-only access is sufficient for read-only views. If authentication
is added, it should not make routine greenhouse operation frustrating.
Operators should not need to log in every time they refresh the dashboard or
reopen it during normal local use.

If Flask is used, the preferred direction is cookie-based session
authentication with a "remember me" token. If PHP is used, the equivalent
session-cookie and persistent-login pattern would be preferred. A heavy
identity system is not needed for the current project scope.

Write actions such as overrides or schedule edits need a higher bar than
read-only status pages. Those actions should have authentication, CSRF
protection, and clear operator feedback before they are added to the new
dashboard.

## Configuration Editing

"Dashboard configuration editing" means allowing the web interface to change
project settings, such as:

- schedule temperatures and ranges stored in SQL
- manual override values
- sensor display names and location labels
- GPIO pin assignments
- controller paths and service settings
- alert thresholds and recipients

These are different risk levels. Schedule values, overrides, and alert
thresholds are reasonable future dashboard features if protected and tested.
GPIO pins, file paths, database credentials, and service settings should
probably stay as file/manual setup tasks for now because mistakes there can
break the controller or create unsafe actuator behavior.

The preferred editing roadmap is:

1. schedule editing plus ventilation fan and window overrides
2. alert thresholds and alert recipients
3. sensor identification, assignment, and display labels

Schedule editing needs validation before it is exposed in the modern dashboard:

- the four schedule periods should be contiguous across the day
- schedule periods should not overlap
- each schedule period should have a valid start and end time
- temperature targets and hysteresis/range values should stay within sane
  greenhouse operating limits
- heater/low-temperature settings should not conflict with fan/window cooling
  settings
- fan and window setpoints should not be set to extreme values that could leave
  the greenhouse unsafe

Recommended first-pass schedule limits:

| Setting | Allowed range | Notes |
| --- | ---: | --- |
| `lowtemp` | 2 C to 18 C | `6 C` is the safer project default. |
| `hightemp` | 18 C to 40 C | Allows warm-climate and unusual crop flexibility without permitting extreme values. |
| `windowtemp` | 18 C to 40 C | Same guardrail as ventilation fan cooling. |
| `lowtemprange` | 0.5 C to 6 C | Prevents heater hysteresis from becoming too narrow or too wide. |
| `hightemprange` | 1 C to 8 C | Keeps fan hysteresis useful without allowing large temperature swings. |
| `windowtemprange` | 1 C to 10 C | Allows wider window hysteresis because windows can have slower physical response and more overshoot. |

Recommended relationship rules:

- `lowtemp` should be at least 3 C below both `hightemp` and `windowtemp`.
- `lowtemp + lowtemprange` should be at least 2 C below the lower of
  `hightemp` and `windowtemp`.
- `hightemp` and `windowtemp` can be close together, but should normally be
  within 5 C of each other unless the operator intentionally confirms an
  advanced or unusual setup.
- Range values must be positive.

The validation should protect against obvious mistakes while still giving
operators room to customize the greenhouse for different crops, seasons, and
operating styles. Borderline values can produce warnings, while values that
make the heating and cooling logic fight each other should be blocked.

Project default schedule values should remain in the SQL schema used for new
installs. The dashboard should not become a second source of default truth.
Once schedule editing exists, the dashboard may offer a "reset to project
defaults" helper, but that helper should read from a documented defaults source
or shared migration data rather than carrying unrelated hard-coded values.

Window and ventilation fan overrides need less validation than schedules.
Overrides are often used for a specific operator need, so validation should
focus on valid states, reasonable expiration times, and clear operator feedback
rather than blocking unusual but intentional actions.

GPIO assignments, controller paths, and service settings should not be exposed
through the dashboard at this stage. They may be reconsidered later, but only
with strong validation and clear recovery behavior.

For the first modern dashboard prototype, configuration editing should be out
of scope. A read-only configuration review page would still be useful because
it can show what the controller is currently using without allowing accidental
changes.

## Soak-Test Support

Future soak-test reports can remain static HTML or markdown artifacts rather
than becoming normal operator dashboard pages. They are primarily development
and release-validation tools.

However, the dashboard may eventually include a simple way to record timestamped
operator notes during a soak test. These notes could capture door openings,
maintenance, weather observations, manual overrides, or unusual greenhouse
behavior, and would make later log analysis easier.

Until that feature exists, soak-test notes can continue to be recorded in a
plain text or markdown file.

## Recommended Direction

The best next step is probably a staged approach:

1. Keep nginx, Cacti, and the existing PHP dashboard available.
2. Create a small modern dashboard surface without changing controller logic.
3. Start with a read-only SCADA-style status page for desktop, with responsive
   tablet and phone layouts.
4. Add manual override controls only after the read-only dashboard is stable.
5. Decide between structured PHP and Flask after the first read-only prototype.

For a low-risk first prototype, two options stand out:

- Structured PHP refresh: fastest and lightest, with the least infrastructure
  change.
- Flask behind nginx: cleaner long-term fit with the Python project, especially
  if future tools like sensor assignment and soak-test reports become web
  workflows.

The chosen first prototype direction is a small Flask app behind nginx. This
does not commit the project permanently to Flask; it gives us a practical way
to evaluate how it looks, runs, and feels on the Raspberry Pi while keeping
Cacti and the legacy PHP dashboard available during transition.

## Open Questions

- Should embedded Cacti graph pages use direct graph image links alone, or
  small wrapper pages that keep the dashboard navigation consistent?
