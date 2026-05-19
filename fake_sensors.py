#!/usr/bin/env python3
#################################################################
# Greenhouse Fake Temperature Injector                          #
# Created for testing greenhouse thermostat controller          #
#                                                               #
# Purpose:                                                      #
# Inject fake temperature readings with current timestamps      #
# into the greenhouse MySQL database so the thermostat          #
# controller can run without physical sensors attached.         #
#################################################################

import time
import math
import random
import configparser
from datetime import datetime, UTC

import pymysql as mdb


# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────

CONFIG_FILE = "/home/pi/py3refactor/greenhouse.conf"

# Update interval in seconds
UPDATE_INTERVAL = 10

# Enable changing temperatures over time
SIMULATE_DAY_NIGHT_CYCLE = True

# Base temperatures
BASE_INSIDE_TEMP = 22.0
BASE_OUTSIDE_TEMP = 10.0
BASE_WOODSTOVE_TEMP = 35.0


# ─────────────────────────────────────────────────────────────
# Database configuration
# ─────────────────────────────────────────────────────────────

config = configparser.ConfigParser()
config.read(CONFIG_FILE)

DB_HOST = config["database"]["host"]
DB_USER = config["database"]["user"]
DB_PASSWORD = config["database"]["password"]
DB_NAME = config["database"]["database"]


# ─────────────────────────────────────────────────────────────
# Sensor IDs from your database layout
# ─────────────────────────────────────────────────────────────
#
# Based on your thermostat code:
#
# 0 = Back sensor
# 1 = Front sensor
# 2 = Outside sensor
# 3 = (unused/unknown)
# 4 = Average sensor
# 5 = Woodstove sensor
#
# Adjust these if your DB layout differs.
# ─────────────────────────────────────────────────────────────

SENSOR_BACK = 1
SENSOR_FRONT = 2
SENSOR_OUTSIDE = 3
SENSOR_UNUSED = 4
SENSOR_AVG = 5
SENSOR_WOODSTOVE = 6


# ─────────────────────────────────────────────────────────────
# Database helper
# ─────────────────────────────────────────────────────────────

def get_db_connection():
    return mdb.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        connect_timeout=5,
        autocommit=True,
    )


# ─────────────────────────────────────────────────────────────
# Temperature helpers
# ─────────────────────────────────────────────────────────────

def c_to_f(temp_c):
    return round((temp_c * 9 / 5) + 32, 1)


def generate_temperatures():
    """
    Generate realistic changing greenhouse temperatures.
    """

    if SIMULATE_DAY_NIGHT_CYCLE:
        # Slow sine wave temperature drift over time
        cycle = math.sin(time.time() / 300)

        inside_temp = BASE_INSIDE_TEMP + (cycle * 4)
        outside_temp = BASE_OUTSIDE_TEMP + (cycle * 8)
    else:
        inside_temp = BASE_INSIDE_TEMP
        outside_temp = BASE_OUTSIDE_TEMP

    # Add small random variation
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


# ─────────────────────────────────────────────────────────────
# Database update
# ─────────────────────────────────────────────────────────────

def update_sensor(sensor_id, temp_c):
    """
    Update one sensor row in currenttemp table.
    """

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
            cur.execute(
                query,
                (
                    str(temp_c),
                    str(temp_f),
                    now,
                    sensor_id,
                ),
            )

    finally:
        if con:
            con.close()


# ─────────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────────

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
