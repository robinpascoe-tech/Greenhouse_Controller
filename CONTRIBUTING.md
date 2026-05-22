# Contributing

Thank you for your interest in improving Greenhouse Controller.

This project is intended to be useful to greenhouse builders, hobbyists,
researchers, and anyone interested in practical Raspberry Pi automation. Clear
bug reports, documentation improvements, wiring notes, simulations, and focused
code changes are all welcome.

## License

Greenhouse Controller is licensed under the GNU General Public License v3.0 or
later.

By submitting a contribution, you agree that your contribution is provided under
the same project license: GPL-3.0-or-later. This keeps the project and derived
distributed versions available under the same free software terms.

## Before Opening A Pull Request

- Keep changes focused on one topic.
- Avoid committing secrets, live credentials, private hostnames, or local config
  files.
- Update documentation when paths, schema, GPIO behavior, configuration, or
  operational behavior changes.
- For Python changes, run:

```bash
python3 -m py_compile scripts/*.py tools/*.py
```

- For controller behavior changes, run the simulation harness when possible:

```bash
python3 tools/simulation_harness.py
```

## Safety Notes

This project can control heaters, fans, relay boards, and motorized windows.
Changes that affect GPIO state, fail-safe behavior, temperature thresholds, or
database-driven control decisions should be tested carefully before use on real
hardware.

When proposing safety-related changes, please describe:

- what behavior changed
- how you tested it
- what failure mode the change is intended to handle

