# Greenhouse Controller Install Guide

This guide assumes a Raspberry Pi running Raspberry Pi OS Trixie with MariaDB
installed locally on the same Pi.

The default install path used by the scripts and sample systemd service is:

```text
/home/pi/Greenhouse_Controller
```

## 1. Install OS Packages

From the repository root:

```bash
sudo apt update
xargs -a apt-packages.txt sudo apt install -y
```

This installs Python, PyMySQL, the Raspberry Pi GPIO compatibility package, and
MariaDB server.

If you are cloning directly from GitHub on a minimal image, install Git first:

```bash
sudo apt install git
```

## 2. Enable 1-Wire Sensors

DS18B20 sensors use the Linux 1-Wire interface. On Raspberry Pi OS Trixie, add
this line to `/boot/firmware/config.txt` if it is not already present:

```text
dtoverlay=w1-gpio
```

Then reboot:

```bash
sudo reboot
```

After reboot, connected DS18B20 sensors should appear under:

```text
/sys/bus/w1/devices/
```

The sensor paths in `scripts/read_sensors.py` are examples from the original
greenhouse. Update the `SENSORS` map to match your sensor IDs.

## 3. Install The Repository

Clone or copy the repository to the expected path:

```bash
cd /home/pi
git clone https://github.com/robinpascoe-tech/Greenhouse_Controller.git Greenhouse_Controller
cd /home/pi/Greenhouse_Controller
```

Repository: [robinpascoe-tech/Greenhouse_Controller](https://github.com/robinpascoe-tech/Greenhouse_Controller)

For release-candidate greenhouse testing, check out the current stable tag:

```bash
git fetch --all --tags
git checkout v0.9.1
```

If you use a different path, update:

- `config/greenhouse-controller.service.example`
- config/log paths in the Python scripts
- cron examples in the docs/scripts

## 4. Configure MariaDB

Start and enable MariaDB:

```bash
sudo systemctl enable --now mariadb
```

Run the MariaDB secure-install helper:

```bash
sudo mariadb-secure-installation
```

Recommended answers for a private Raspberry Pi greenhouse controller:

```text
Switch to unix_socket authentication: Yes
Change the root password: optional if unix_socket is enabled
Remove anonymous users: Yes
Disallow root login remotely: Yes
Remove test database: Yes
Reload privilege tables: Yes
```

MariaDB should only need local access for this project. Confirm it is listening
locally:

```bash
sudo ss -ltnp | grep 3306
```

For a typical local-only setup, MariaDB should bind to `127.0.0.1`. On Debian
/ Raspberry Pi OS Trixie, the bind address is commonly configured in:

```text
/etc/mysql/mariadb.conf.d/50-server.cnf
```

If needed, set:

```ini
bind-address = 127.0.0.1
```

Then restart MariaDB:

```bash
sudo systemctl restart mariadb
```

Verify admin access:

```bash
sudo mariadb -e "SELECT VERSION();"
```

## 5. Create The Database

For a fresh install, edit `sql/schema.sql` and replace every
`change_this_password` placeholder with a real password for the `greenhouse_app`
SQL user.

Generate a password, for example:

```bash
openssl rand -base64 24
```

Then import the schema:

```bash
sudo mariadb < sql/schema.sql
```

For an existing legacy greenhouse database, review and run:

```bash
sudo mariadb greenhouse < sql/migrate_schema.sql
```

Use an admin/root MariaDB account for schema creation and migrations. The Python
scripts should use the limited `greenhouse_app` user.

Verify the app user can connect:

```bash
mariadb -u greenhouse_app -p greenhouse -e "SELECT COUNT(*) FROM settings;"
```

The schema creates both `greenhouse_app`@`localhost` and
`greenhouse_app`@`127.0.0.1`. Keeping both avoids surprises if a client library
connects through the Unix socket for `localhost` or TCP for `127.0.0.1`.

## 6. Create Runtime Config

Copy the example config:

```bash
cp config/greenhouse.conf.example greenhouse.conf
chmod 600 greenhouse.conf
```

Edit `greenhouse.conf` and set the database password to the same value used in
`schema.sql` or `migrate_schema.sql`:

```ini
[database]
host = localhost
user = greenhouse_app
password = your_database_password
database = greenhouse
```

Email alerts are disabled by default. Leave `[alerts] enabled = false` until you
are ready to configure SMTP credentials.

## 7. Test The Scripts

Compile-check the Python files:

```bash
python3 -m py_compile scripts/*.py tools/*.py
```

Run the sensor reader once:

```bash
python3 scripts/read_sensors.py
```

Without attached 1-Wire sensors, this should log failures but should not crash.

Run the sensor health script:

```bash
python3 scripts/sensor_health.py
```

The main controller drives GPIO outputs. Only run it when the relay wiring and
GPIO pin assignments have been reviewed:

```bash
python3 scripts/greenhouse_controller.py
```

Stop with `CTRL+C`; the controller should run its safe shutdown path.

## 8. Install systemd Service

Copy the sample service:

```bash
sudo cp config/greenhouse-controller.service.example \
  /etc/systemd/system/greenhouse-controller.service
```

Reload systemd:

```bash
sudo systemctl daemon-reload
```

Start the controller:

```bash
sudo systemctl start greenhouse-controller
```

Check logs:

```bash
journalctl -u greenhouse-controller -f
```

Enable automatic startup:

```bash
sudo systemctl enable greenhouse-controller
```

Stop the controller:

```bash
sudo systemctl stop greenhouse-controller
```

The service uses `SIGTERM`, which the controller handles as a safe shutdown.

## 9. Suggested Cron Jobs

Sensor reading should run frequently, for example every minute:

```cron
* * * * * /usr/bin/python3 /home/pi/Greenhouse_Controller/scripts/read_sensors.py
```

For fresher readings, a second offset run can be added:

```cron
* * * * * sleep 30; /usr/bin/python3 /home/pi/Greenhouse_Controller/scripts/read_sensors.py
```

Sensor health can run less often:

```cron
*/15 * * * * /usr/bin/python3 /home/pi/Greenhouse_Controller/scripts/sensor_health.py
```

Status log cleanup can run daily:

```cron
0 3 * * * /usr/bin/python3 /home/pi/Greenhouse_Controller/scripts/cleanup_status_log.py
```

Sensor diagnostics cleanup can run daily. This keeps raw sensor history bounded
while preserving enough recent data for troubleshooting:

```cron
15 3 * * * /usr/bin/python3 /home/pi/Greenhouse_Controller/scripts/cleanup_sensor_diagnostics.py
```

Edit cron with:

```bash
crontab -e
```

## 10. Optional Simulation Harness

The simulation harness creates and drops a throwaway database. It requires an
admin MariaDB password supplied through an environment variable:

```bash
export GREENHOUSE_TEST_DB_ROOT_PASSWORD='your-root-password'
python3 tools/simulation_harness.py
```

The harness records GPIO calls instead of moving real relays.

## 11. Useful Checks

Check service status:

```bash
systemctl status greenhouse-controller
```

Check controller log file:

```bash
tail -f /home/pi/Greenhouse_Controller/thermostat.log
```

Check sensor log file:

```bash
tail -f /home/pi/Greenhouse_Controller/greenhouse_sensors.log
```

Inspect GPIO state without changing outputs:

```bash
python3 tools/gpio_monitor.py
```
