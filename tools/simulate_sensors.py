#!/usr/bin/env python3
"""
Inject simulated temperatures into the currenttemp table.

This tool is useful when developing without DS18B20 sensors attached. It only
updates the operational currenttemp rows; it does not create sensor_diagnostics
history for sensor_health.py.
"""

import configparser
import math
import random
import time
from datetime import UTC, datetime

import pymysql as mdb


# ============================================================
# CONFIGURATION
# ============================================================

CONFIG_FILE = "/home/pi/Greenhouse_Controller/greenhouse.conf"
UPDATE_INTERVAL = 10

# When enabled, temperatures drift on a gentle sine wave instead of staying
# fixed at the base values below.
SIMULATE_DAY_NIGHT_CYCLE = True

BASE_INSIDE_TEMP = 22.0
BASE_OUTSIDE_TEMP = 10.0
BASE_WOODSTOVE_TEMP = 35.0


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

config = configparser.ConfigParser()
config.read(CONFIG_FILE)

DB_HOST = config["database"]["host"]
DB_USER = config["database"]["user"]
DB_PASSWORD = config["database"]["password"]
DB_NAME = config["database"]["database"]


# ============================================================
# CURRENTTEMP ROW IDS
# ============================================================

# These IDs match sql/schema.sql. Runtime code primarily uses Name, but this
# helper updates by id so it can leave the Name values alone.
SENSOR_BACK = 1
SENSOR_FRONT = 2
SENSOR_OUTSIDE = 3
SENSOR_UNUSED = 4
SENSOR_AVG = 5
SENSOR_WOODSTOVE = 6


# ============================================================
# HELPERS
# ============================================================

def get_db_connection():
    """Open an autocommit connection for simple row updates."""
    return mdb.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        connect_timeout=5,
        autocommit=True,
    )


def c_to_f(temp_c):
    """Convert Celsius to Fahrenheit for currenttemp.temperatureF."""
    return round((temp_c * 9 / 5) + 32, 1)


def generate_temperatures():
    """Generate a small, smooth set of test temperatures."""
    if SIMULATE_DAY_NIGHT_CYCLE:
        cycle = math.sin(time.time() / 300)
        inside_temp = BASE_INSIDE_TEMP + (cycle * 4)
        outside_temp = BASE_OUTSIDE_TEMP + (cycle * 8)
    else:
        inside_temp = BASE_INSIDE_TEMP
        outside_temp = BASE_OUTSIDE_TEMP

    front_temp = inside_temp + random.uniform(-0.5, 0.5)
    back_temp = inside_temp + random.uniform(-0.5, 0.5)
    avg_temp = (front_temp + back_temp) / 2
    woodstove_temp = BASE_WOODSTOVE_TEMP + random.uniform(-2, 2)

    return {
        SENSOR_BACK: round(back_temp, 1),
        SENSOR_FRONT: round(front_temp, 1),
        SENSOR_OUTSIDE: round(outside_temp, 1),
        SENSOR_UNUSED: round(inside_temp, 1),
        SENSOR_AVG: round(avg_temp, 1),
        SENSOR_WOODSTOVE: round(woodstove_temp, 1),
    }


def update_sensor(sensor_id, temp_c):
    """Update one currenttemp row with Celsius, Fahrenheit, and timestamp."""
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    temp_f = c_to_f(temp_c)

    query = """
        UPDATE currenttemp
        SET
            temperature = %s,
            temperatureF = %s,
            timestamp = %s
        WHERE id = %s
    """

    con = None
    try:
        con = get_db_connection()
        with con.cursor() as cur:
            cur.execute(query, (str(temp_c), str(temp_f), now, sensor_id))
    finally:
        if con:
            con.close()


# ============================================================
# MAIN LOOP
# ============================================================

def main():
    print("Starting greenhouse fake sensor injector...")
    print(f"Updating temperatures every {UPDATE_INTERVAL} seconds.")
    print("Press CTRL+C to stop.\n")

    while True:
        try:
            temps = generate_temperatures()

            for sensor_id, temp_c in temps.items():
                update_sensor(sensor_id, temp_c)

            print(
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
                f"Front: {temps[SENSOR_FRONT]:.1f}C | "
                f"Back: {temps[SENSOR_BACK]:.1f}C | "
                f"Avg: {temps[SENSOR_AVG]:.1f}C | "
                f"Outside: {temps[SENSOR_OUTSIDE]:.1f}C"
            )

            time.sleep(UPDATE_INTERVAL)

        except KeyboardInterrupt:
            print("\nStopping fake sensor injector.")
            break

        except Exception as e:
            print(f"ERROR: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
