#!/usr/bin/env python3
"""
Remove old sensor_diagnostics rows so raw sensor history does not grow forever.

Typical cron entry:
    15 3 * * * /usr/bin/python3 /home/pi/Greenhouse_Controller/scripts/cleanup_sensor_diagnostics.py
"""

import configparser
from datetime import datetime, timezone, timedelta

import pymysql as mdb


# ============================================================
# CONFIGURATION
# ============================================================

# sensor_health.py currently evaluates 1h, 6h, and 24h windows. Keep retention
# above 1 day so the 24-hour drift window remains meaningful. The default of 30
# days leaves plenty of recent history for troubleshooting while bounding table
# size.
RETENTION_DAYS = 30
CONFIG_FILE = "/home/pi/Greenhouse_Controller/greenhouse.conf"


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

_db_config = configparser.ConfigParser()
_db_config.read(CONFIG_FILE)

try:
    DB_HOST = _db_config["database"]["host"]
    DB_USER = _db_config["database"]["user"]
    DB_PASSWORD = _db_config["database"]["password"]
    DB_NAME = _db_config["database"]["database"]
except KeyError:
    # Placeholder fallback for development systems without config.
    DB_HOST = "localhost"
    DB_USER = "greenhouse_app"
    DB_PASSWORD = "change_this_password"
    DB_NAME = "greenhouse"


# ============================================================
# CLEANUP
# ============================================================

def cleanup_old_diagnostics():
    """Delete sensor_diagnostics rows older than RETENTION_DAYS."""
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
        days=RETENTION_DAYS
    )

    print(f"Deleting sensor_diagnostics records older than: {cutoff}")

    con = mdb.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        connect_timeout=5,
        autocommit=False,
        init_command="SET time_zone = '+00:00'",
    )

    try:
        with con.cursor() as cur:
            cur.execute(
                """
                DELETE FROM sensor_diagnostics
                WHERE timestamp < %s
                """,
                (cutoff,),
            )
            deleted_rows = cur.rowcount

        con.commit()
        print(f"Deleted rows: {deleted_rows}")

    except Exception as e:
        print(f"Cleanup failed: {e}")
        con.rollback()

    finally:
        con.close()


if __name__ == "__main__":
    cleanup_old_diagnostics()
