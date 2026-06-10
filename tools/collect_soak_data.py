#!/usr/bin/env python3
"""
Collect greenhouse soak-test evidence into a compressed archive.

This tool is intended to run on the Raspberry Pi after a soak test. It gathers
logs, notes, service state, Git metadata, SQL schema files, a database snapshot,
and a MariaDB dump without printing database credentials.
"""

from __future__ import annotations

import argparse
import configparser
import os
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

import pymysql


DEFAULT_REPO = Path("/home/pi/Greenhouse_Controller")
DEFAULT_OUTPUT_ROOT = Path("/tmp")
DEFAULT_SINCE = "4 days ago"


def utc_stamp() -> str:
    """Return a compact UTC timestamp suitable for filenames."""

    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_command(command, output_file: Path, cwd: Path | None = None) -> None:
    """Run a command and write stdout/stderr to a file."""

    with output_file.open("w", encoding="utf-8", errors="replace") as handle:
        try:
            subprocess.run(
                command,
                cwd=cwd,
                stdout=handle,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            print(f"ERROR: command not found: {exc.filename}", file=handle)


def copy_optional(src: Path, dst: Path) -> None:
    """Copy a file if present."""

    if src.exists():
        shutil.copy2(src, dst)


def copy_glob(src_dir: Path, pattern: str, dst_dir: Path) -> None:
    """Copy matching files from a directory if they exist."""

    for path in src_dir.glob(pattern):
        if path.is_file():
            shutil.copy2(path, dst_dir / path.name)


def read_database_config(repo: Path) -> dict[str, str]:
    """Read MariaDB connection settings from greenhouse.conf."""

    config_path = repo / "greenhouse.conf"
    cfg = configparser.ConfigParser()
    cfg.read(config_path)
    return {
        "host": cfg["database"]["host"],
        "user": cfg["database"]["user"],
        "password": cfg["database"]["password"],
        "database": cfg["database"]["database"],
    }


def connect_db(db_config: dict[str, str]):
    """Open a PyMySQL connection using project database settings."""

    return pymysql.connect(
        host=db_config["host"],
        user=db_config["user"],
        password=db_config["password"],
        database=db_config["database"],
        cursorclass=pymysql.cursors.DictCursor,
    )


def write_query(cur, label: str, sql: str, handle) -> None:
    """Write query results to the database snapshot file."""

    print(f"\n## {label}", file=handle)
    try:
        cur.execute(sql)
        for row in cur.fetchall():
            print(row, file=handle)
    except Exception as exc:
        print(f"ERROR: {exc!r}", file=handle)


def write_database_snapshot(db_config: dict[str, str], output_file: Path) -> None:
    """Write compact database state useful for quick soak-test triage."""

    queries = [
        ("utc_now", "SELECT UTC_TIMESTAMP() AS utc_now"),
        ("tables", "SHOW TABLES"),
        ("currenttemp", "SELECT * FROM currenttemp ORDER BY id"),
        ("status", "SELECT * FROM status ORDER BY id"),
        ("overrides", "SELECT * FROM overrides ORDER BY id"),
        ("settings", "SELECT * FROM settings ORDER BY id"),
        (
            "recent_status_log",
            "SELECT * FROM status_log ORDER BY timestamp DESC LIMIT 200",
        ),
        (
            "recent_sensor_health",
            "SELECT * FROM sensor_health ORDER BY timestamp DESC LIMIT 200",
        ),
        (
            "sensor_diagnostics_24h_summary",
            """
            SELECT sensor_name, COUNT(*) AS count,
                   SUM(COALESCE(failure_count, 0)) AS failure_count,
                   SUM(COALESCE(crc_failures, 0)) AS crc_failures,
                   MIN(timestamp) AS first_read,
                   MAX(timestamp) AS latest_read
            FROM sensor_diagnostics
            WHERE timestamp >= UTC_TIMESTAMP() - INTERVAL 24 HOUR
            GROUP BY sensor_name
            ORDER BY sensor_name
            """,
        ),
        (
            "sensor_diagnostics_recent_failures",
            """
            SELECT *
            FROM sensor_diagnostics
            WHERE timestamp >= UTC_TIMESTAMP() - INTERVAL 24 HOUR
              AND (
                  COALESCE(failure_count, 0) > 0
                  OR COALESCE(crc_failures, 0) > 0
              )
            ORDER BY timestamp DESC
            LIMIT 200
            """,
        ),
    ]

    with output_file.open("w", encoding="utf-8", errors="replace") as handle:
        print(f"snapshot_utc {datetime.now(timezone.utc).isoformat()}", file=handle)
        try:
            with connect_db(db_config) as db:
                with db.cursor() as cur:
                    for label, sql in queries:
                        write_query(cur, label, sql, handle)
        except Exception as exc:
            print(f"ERROR: could not collect database snapshot: {exc!r}", file=handle)


def write_mysqldump(db_config: dict[str, str], output_file: Path, err_file: Path) -> None:
    """Run mysqldump while passing the password through the environment."""

    env = os.environ.copy()
    env["MYSQL_PWD"] = db_config["password"]
    command = [
        "mysqldump",
        "--single-transaction",
        "--skip-comments",
        "-h",
        db_config["host"],
        "-u",
        db_config["user"],
        db_config["database"],
    ]

    with output_file.open("w", encoding="utf-8", errors="replace") as stdout:
        with err_file.open("w", encoding="utf-8", errors="replace") as stderr:
            try:
                subprocess.run(
                    command,
                    env=env,
                    stdout=stdout,
                    stderr=stderr,
                    text=True,
                    check=False,
                )
            except FileNotFoundError as exc:
                print(f"ERROR: command not found: {exc.filename}", file=stderr)


def write_database_artifacts(repo: Path, base: Path) -> None:
    """Write database evidence, preserving collection output if MariaDB is down."""

    try:
        db_config = read_database_config(repo)
    except Exception as exc:
        (base / "database_snapshot.txt").write_text(
            f"ERROR: could not read greenhouse.conf database settings: {exc!r}\n",
            encoding="utf-8",
        )
        (base / "mysqldump.err").write_text(
            "ERROR: skipped mysqldump because database settings could not be read\n",
            encoding="utf-8",
        )
        (base / "greenhouse_dump.sql").write_text("", encoding="utf-8")
        return

    write_database_snapshot(db_config, base / "database_snapshot.txt")
    write_mysqldump(
        db_config,
        base / "greenhouse_dump.sql",
        base / "mysqldump.err",
    )


def collect(args) -> Path:
    """Collect soak-test files and return the created archive path."""

    repo = args.repo.resolve()
    stamp = utc_stamp()
    output_root = args.output_root.resolve()
    base = output_root / f"greenhouse_soak_{stamp}"
    archive = output_root / f"{base.name}.tar.gz"

    logs_dir = base / "logs"
    repo_dir = base / "repo"
    system_dir = base / "system"
    sql_dir = base / "sql"

    for path in (logs_dir, repo_dir, system_dir, sql_dir):
        path.mkdir(parents=True, exist_ok=True)

    with (base / "collection_info.txt").open(
        "w", encoding="utf-8", errors="replace"
    ) as handle:
        print(f"collection_utc={stamp}", file=handle)
        print(f"repo={repo}", file=handle)
        print(f"since={args.since}", file=handle)

    run_command(["date", "-u"], base / "collection_utc_date.txt")
    run_command(["date"], base / "collection_local_date.txt")
    run_command(["hostname"], base / "hostname.txt")
    run_command(["uptime"], base / "uptime.txt")

    if (repo / ".git").exists():
        run_command(["git", "branch", "--show-current"], repo_dir / "branch.txt", repo)
        run_command(
            ["git", "describe", "--tags", "--always", "--dirty"],
            repo_dir / "describe.txt",
            repo,
        )
        run_command(["git", "status", "--short", "--branch"], repo_dir / "status.txt", repo)
        run_command(
            ["git", "log", "--oneline", "--decorate", "-n", "20"],
            repo_dir / "recent_commits.txt",
            repo,
        )

    run_command(
        ["systemctl", "status", "greenhouse-controller.service", "--no-pager"],
        system_dir / "greenhouse-controller.status.txt",
    )
    run_command(
        [
            "systemctl",
            "show",
            "greenhouse-controller.service",
            "--property=ActiveState,SubState,MainPID,NRestarts,ExecMainStartTimestamp",
        ],
        system_dir / "greenhouse-controller.show.txt",
    )
    run_command(
        [
            "journalctl",
            "-u",
            "greenhouse-controller.service",
            "--since",
            args.since,
            "--no-pager",
        ],
        system_dir / "greenhouse-controller.journal.txt",
    )
    run_command(["crontab", "-l"], system_dir / "crontab.txt")
    run_command(["systemctl", "list-timers", "--all", "--no-pager"], system_dir / "timers.txt")
    run_command(["dmesg", "--ctime"], system_dir / "dmesg.txt")
    run_command(["vcgencmd", "get_throttled"], system_dir / "vcgencmd_get_throttled.txt")

    copy_optional(repo / "notes.md", base / "notes.md")
    copy_optional(repo / "notes.md.save", base / "notes.md.save")
    copy_glob(repo, "thermostat.log*", logs_dir)
    copy_glob(repo, "greenhouse_sensors.log*", logs_dir)
    copy_glob(repo / "sql", "*.sql", sql_dir)

    write_database_artifacts(repo, base)

    with tarfile.open(archive, "w:gz") as tar:
        tar.add(base, arcname=base.name)

    if not args.keep_unpacked:
        shutil.rmtree(base)

    return archive


def parse_args():
    parser = argparse.ArgumentParser(
        description="Collect greenhouse soak-test logs, state, and database dump."
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=DEFAULT_REPO,
        help=f"Greenhouse_Controller checkout path. Default: {DEFAULT_REPO}",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help=f"Directory where the archive is created. Default: {DEFAULT_OUTPUT_ROOT}",
    )
    parser.add_argument(
        "--since",
        default=DEFAULT_SINCE,
        help='journalctl --since value. Default: "4 days ago"',
    )
    parser.add_argument(
        "--keep-unpacked",
        action="store_true",
        help="Keep the unpacked collection directory alongside the archive.",
    )
    return parser.parse_args()


def main() -> int:
    archive = collect(parse_args())
    print(archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
