#!/usr/bin/env python3
"""
Remove old status_log rows so the greenhouse database does not grow forever.

Typical cron entry:
    0 3 * * * /usr/bin/python3 /home/pi/Greenhouse_Controller/scripts/cleanup_status_log.py
"""

import configparser
from datetime import datetime, timedelta

import pymysql as mdb


# ============================================================
# CONFIGURATION
# ============================================================

RETENTION_DAYS = 14
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

def cleanup_old_logs():
    """Delete status_log rows older than RETENTION_DAYS."""
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)

    print(f"Deleting records older than: {cutoff}")

    con = mdb.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        connect_timeout=5,
        autocommit=False,
    )

    try:
        with con.cursor() as cur:
            cur.execute(
                """
                DELETE FROM status_log
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
    cleanup_old_logs()
