#!/usr/bin/env python3
"""
Replay sensor_health.py across historical diagnostic data.

The health engine uses rolling 1h/6h/24h windows based on datetime.now(). This
helper freezes that clock at fixed checkpoints so an imported soak-test database
can be evaluated as if sensor_health.py had run during the original test.
"""

import argparse
import importlib
import sys
from datetime import datetime as real_datetime, timezone, timedelta
from pathlib import Path

import pymysql


def parse_utc(value):
    """Parse an ISO-like timestamp and return an aware UTC datetime."""
    text = value.strip().replace("T", " ").replace("Z", "+00:00")
    dt = real_datetime.fromisoformat(text)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def checkpoints(start, end, interval_minutes):
    """Yield UTC checkpoints from start through end."""
    current = start
    step = timedelta(minutes=interval_minutes)
    while current <= end:
        yield current
        current += step


def connect(sensor_health, database):
    """Open a connection using sensor_health.py's configured credentials."""
    return pymysql.connect(
        host=sensor_health.DB_HOST,
        user=sensor_health.DB_USER,
        password=sensor_health.DB_PASSWORD,
        database=database,
        cursorclass=pymysql.cursors.Cursor,
        connect_timeout=5,
        autocommit=True,
    )


def clear_derived(sensor_health, database):
    """Remove previous health output so replay results are clean."""
    with connect(sensor_health, database) as con:
        with con.cursor() as cur:
            for table in ("sensor_health", "sensor_state", "sensor_alerts"):
                cur.execute(f"TRUNCATE TABLE {table}")


def disable_alert_side_effects(sensor_health):
    """Prevent replay runs from sending or printing simulated alerts."""
    sensor_health.ALERTS_ENABLED = False
    sensor_health.alert = lambda cur, sensor, status, score: None


def patch_clock(sensor_health, frozen_now):
    """Replace sensor_health.datetime with a datetime subclass frozen at now."""

    class FrozenDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return frozen_now.replace(tzinfo=None)
            return frozen_now.astimezone(tz)

    sensor_health.datetime = FrozenDateTime


def summarize(sensor_health, database):
    """Return replay summaries and latest health rows."""
    with connect(sensor_health, database) as con:
        with con.cursor() as cur:
            cur.execute(
                """
                SELECT sensor_name, status, COUNT(*), ROUND(AVG(health_score), 1),
                       MIN(health_score), MAX(health_score)
                FROM sensor_health
                GROUP BY sensor_name, status
                ORDER BY sensor_name, status
                """
            )
            status_summary = cur.fetchall()

            cur.execute(
                """
                SELECT h.sensor_name, h.status, h.health_score, h.notes, h.timestamp
                FROM sensor_health h
                JOIN (
                    SELECT sensor_name, MAX(timestamp) AS max_ts
                    FROM sensor_health
                    GROUP BY sensor_name
                ) latest
                  ON latest.sensor_name = h.sensor_name
                 AND latest.max_ts = h.timestamp
                ORDER BY h.sensor_name
                """
            )
            latest_rows = cur.fetchall()

            cur.execute(
                """
                SELECT sensor_name, notes, COUNT(*)
                FROM sensor_health
                WHERE notes <> 'ok'
                GROUP BY sensor_name, notes
                ORDER BY sensor_name, COUNT(*) DESC, notes
                """
            )
            note_summary = cur.fetchall()

    return status_summary, latest_rows, note_summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True)
    parser.add_argument("--start", required=True, help="UTC timestamp")
    parser.add_argument("--end", required=True, help="UTC timestamp")
    parser.add_argument("--interval-minutes", type=int, default=15)
    parser.add_argument("--scripts-dir", default="scripts")
    parser.add_argument("--clear-derived", action="store_true")
    args = parser.parse_args()

    scripts_dir = Path(args.scripts_dir).resolve()
    sys.path.insert(0, str(scripts_dir))
    sensor_health = importlib.import_module("sensor_health")
    sensor_health.DB_NAME = args.database
    disable_alert_side_effects(sensor_health)

    if args.clear_derived:
        clear_derived(sensor_health, args.database)

    start = parse_utc(args.start)
    end = parse_utc(args.end)

    runs = 0
    for frozen_now in checkpoints(start, end, args.interval_minutes):
        patch_clock(sensor_health, frozen_now)
        sensor_health.main()
        runs += 1

    status_summary, latest_rows, note_summary = summarize(sensor_health, args.database)

    print(f"Replay runs: {runs}")
    print("\nStatus summary:")
    for row in status_summary:
        print("\t".join(str(item) for item in row))

    print("\nLatest rows:")
    for row in latest_rows:
        print("\t".join(str(item) for item in row))

    print("\nNon-ok note summary:")
    for row in note_summary:
        print("\t".join(str(item) for item in row))


if __name__ == "__main__":
    main()
