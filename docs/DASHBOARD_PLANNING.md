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
- Embed selected Cacti graph images or pages in dashboard panels if the paths
  are stable.
- Add a "Historical Graphs" section that intentionally hands off to Cacti.

The custom dashboard should focus on live operations, safety, controls, sensor
health, and interpretation. Cacti should continue doing what it does well:
long-term graphing.

## Recommended Direction

The best next step is probably a staged approach:

1. Keep nginx, Cacti, and the existing PHP dashboard available.
2. Create a small modern dashboard surface without changing controller logic.
3. Start with read-only status, temperatures, sensor health, and Cacti links.
4. Add manual override controls only after the read-only dashboard is stable.
5. Decide between structured PHP and Flask after the first read-only prototype.

For a low-risk first prototype, two options stand out:

- Structured PHP refresh: fastest and lightest, with the least infrastructure
  change.
- Flask behind nginx: cleaner long-term fit with the Python project, especially
  if future tools like sensor assignment and soak-test reports become web
  workflows.

My current leaning is Flask for the long-term dashboard, but not as a big
rewrite. A modest Flask app behind nginx, with Cacti preserved and the legacy
PHP dashboard still available during transition, gives the project room to grow
without making the Raspberry Pi carry a heavy web stack.

## Open Questions

- Should the first prototype be read-only?
- Should manual overrides stay in PHP until the new dashboard has auth/CSRF
  protection?
- Should Cacti graphs be embedded or simply linked?
- Should dashboard authentication be local-network-only, HTTP basic auth, or a
  simple login?
- Should dashboard configuration editing be allowed, or should config remain
  file/SQL/manual for now?
- Should future soak-test reports be generated as static HTML, a dashboard
  page, or both?
