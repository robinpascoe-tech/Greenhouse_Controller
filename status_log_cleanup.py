#!/usr/bin/env python3

# Cleanup old status_log entries to prevent database bloat.
# Run this script via CRON, e.g. once per day:
# crontab -e
# 0 3 * * * /usr/bin/python3 /home/pi/py3refactor/status_log_cleanup.py


import pymysql as mdb
from datetime import datetime, timedelta
import configparser

RETENTION_DAYS = 14

# ── Database configuration ─────────────────────────────────────────────────────
# Credentials are read from /home/pi/py3refactor/greenhouse.conf so they are never
# stored in source code.  Example config file:
#
#   [database]
#   host     = localhost
#   user     = greenhouse
#   password = example_password
#   database = greenhouse
#
_db_config = configparser.ConfigParser()
_db_config.read('/home/pi/py3refactor/greenhouse.conf')

try:
    DB_HOST     = _db_config['database']['host']
    DB_USER     = _db_config['database']['user']
    DB_PASSWORD = _db_config['database']['password']
    DB_NAME     = _db_config['database']['database']
except KeyError:
    # Fall back to environment-variable-style defaults for backwards compatibility.
    # Remove this block once the config file is in place.
    DB_HOST     = 'localhost'
    DB_USER     = 'root'
    DB_PASSWORD = 'change_this_password'
    DB_NAME     = 'greenhouse'

def cleanup_old_logs():
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
    cur = con.cursor()

    try:
        cur.execute("""
            DELETE FROM status_log
            WHERE timestamp < %s
        """, (cutoff,))

        con.commit()

        print(f"Deleted rows: {cur.rowcount}")

    except Exception as e:
        print(f"Cleanup failed: {e}")
        con.rollback()

    finally:
        con.close()


if __name__ == "__main__":
    cleanup_old_logs()
