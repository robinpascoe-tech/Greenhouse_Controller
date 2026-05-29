-- Migration for an existing greenhouse database dump from May 21, 2026.
-- Target: align the legacy tables with schema.sql and add the new
-- diagnostics/health/status log tables used by the Python scripts.
--
-- Recommended usage:
--   1. Take a backup first:
--      mariadb-dump -u root -p greenhouse > greenhouse_before_migration.sql
--   2. Run this migration:
--      mariadb -u root -p greenhouse < migrate_schema.sql

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";

CREATE DATABASE IF NOT EXISTS `greenhouse`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `greenhouse`;

START TRANSACTION;

ALTER DATABASE `greenhouse`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- Helper routines for idempotent index cleanup.
-- MariaDB/MySQL ALTER TABLE DROP INDEX fails if the index is absent, so these
-- small procedures make the script safe to run more than once.
-- ---------------------------------------------------------------------------

DROP PROCEDURE IF EXISTS `drop_index_if_exists`;
DROP PROCEDURE IF EXISTS `add_index_if_missing`;

DELIMITER //

CREATE PROCEDURE drop_index_if_exists(
    IN p_table_name VARCHAR(64),
    IN p_index_name VARCHAR(64)
)
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.statistics
        WHERE table_schema = DATABASE()
          AND table_name = p_table_name
          AND index_name = p_index_name
    ) THEN
        SET @sql = CONCAT(
            'ALTER TABLE `',
            REPLACE(p_table_name, '`', '``'),
            '` DROP INDEX `',
            REPLACE(p_index_name, '`', '``'),
            '`'
        );
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END IF;
END//

CREATE PROCEDURE add_index_if_missing(
    IN p_table_name VARCHAR(64),
    IN p_index_name VARCHAR(64),
    IN p_index_sql TEXT
)
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.statistics
        WHERE table_schema = DATABASE()
          AND table_name = p_table_name
          AND index_name = p_index_name
    ) THEN
        SET @sql = CONCAT(
            'ALTER TABLE `',
            REPLACE(p_table_name, '`', '``'),
            '` ADD ',
            p_index_sql
        );
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END IF;
END//

DELIMITER ;

-- ---------------------------------------------------------------------------
-- New runtime/history tables.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS `status_log` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `heater` INT NOT NULL,
    `fan` INT NOT NULL,
    `circfan` INT NOT NULL,
    `window` INT NOT NULL,
    `timestamp` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_status_log_timestamp` (`timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `sensor_diagnostics` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `sensor_name` VARCHAR(64) NOT NULL,
    `timestamp` DATETIME NOT NULL,
    `raw_values` TEXT,
    `median` DECIMAL(6,2),
    `average` DECIMAL(6,2),
    `stddev` DECIMAL(6,3),
    `failure_count` INT,
    `crc_failures` INT NOT NULL DEFAULT 0,
    `notes` VARCHAR(255),
    INDEX `idx_sensor_diagnostics_sensor_time` (`sensor_name`, `timestamp`),
    INDEX `idx_sensor_diagnostics_timestamp` (`timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `sensor_health` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `sensor_name` VARCHAR(64) NOT NULL,
    `timestamp` DATETIME NOT NULL,
    `health_score` INT,
    `status` VARCHAR(32),
    `crc_rate` DECIMAL(6,3),
    `variance` DECIMAL(10,4),
    `drift_short` DECIMAL(10,4),
    `drift_long` DECIMAL(10,4),
    `confidence` DECIMAL(5,2),
    `notes` TEXT,
    INDEX `idx_sensor_health_sensor_time` (`sensor_name`, `timestamp`),
    INDEX `idx_sensor_health_timestamp` (`timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `sensor_alerts` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `sensor_name` VARCHAR(64) NOT NULL,
    `timestamp` DATETIME NOT NULL,
    `alert_type` VARCHAR(32) NOT NULL,
    `message` TEXT,
    INDEX `idx_sensor_alerts_sensor_type_time` (`sensor_name`, `alert_type`, `timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `sensor_state` (
    `sensor_name` VARCHAR(64) PRIMARY KEY,
    `last_status` VARCHAR(32),
    `last_health` INT,
    `ema_health` DECIMAL(6,2),
    `ema_variance` DECIMAL(10,4),
    `last_change_time` DATETIME
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `sensor_profile` (
    `sensor_name` VARCHAR(64) PRIMARY KEY,
    `sensor_type` VARCHAR(32) NOT NULL DEFAULT 'indoor',
    `expected_min` FLOAT,
    `expected_max` FLOAT,
    `normal_variance` FLOAT DEFAULT 1.0,
    `drift_sensitivity` FLOAT DEFAULT 1.0,
    `noise_tolerance` FLOAT DEFAULT 1.0,
    `crc_sensitivity` FLOAT DEFAULT 1.0,
    `learned_mean` FLOAT,
    `learned_variance` FLOAT,
    `last_updated` DATETIME
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------------
-- Legacy tables used directly by greenhouse_controller.py and read_sensors.py.
-- ---------------------------------------------------------------------------

ALTER TABLE `alerts`
  MODIFY `id` INT(11) NOT NULL AUTO_INCREMENT,
  ENGINE=InnoDB,
  DEFAULT CHARSET=latin1,
  COLLATE=latin1_swedish_ci;

ALTER TABLE `currenttemp`
  MODIFY `id` INT(11) NOT NULL AUTO_INCREMENT,
  MODIFY `temperature` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  MODIFY `temperatureF` DECIMAL(10,2) NOT NULL DEFAULT 32.00,
  MODIFY `timestamp` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  MODIFY `Name` VARCHAR(64) NOT NULL,
  ENGINE=InnoDB,
  DEFAULT CHARSET=utf8mb4,
  COLLATE=utf8mb4_unicode_ci;

CALL drop_index_if_exists('currenttemp', 'id');
CALL add_index_if_missing(
  'currenttemp',
  'uk_currenttemp_name',
  'UNIQUE KEY `uk_currenttemp_name` (`Name`)'
);

INSERT INTO `currenttemp` (`id`, `temperature`, `temperatureF`, `timestamp`, `Name`) VALUES
  (1, 0.00, 32.00, '2010-01-01 00:00:00', 'BackTemp'),
  (2, 0.00, 32.00, '2010-01-01 00:00:00', 'FrontTemp'),
  (3, 0.00, 32.00, '2010-01-01 00:00:00', 'OutsideTemp'),
  (4, 0.00, 32.00, '2010-01-01 00:00:00', 'PiTemp'),
  (5, 0.00, 32.00, '2010-01-01 00:00:00', 'AverageInsideTemp'),
  (6, 0.00, 32.00, '2010-01-01 00:00:00', 'WoodstoveTemp')
ON DUPLICATE KEY UPDATE
  `Name` = VALUES(`Name`);

ALTER TABLE `overrides`
  MODIFY `id` INT(11) NOT NULL,
  MODIFY `windowoverride` TINYINT(1) NOT NULL DEFAULT 0,
  MODIFY `windowexpire` DATETIME NOT NULL DEFAULT '2010-01-01 00:00:00',
  MODIFY `fanoverride` TINYINT(1) NOT NULL DEFAULT 0,
  MODIFY `fanexpire` DATETIME NOT NULL DEFAULT '2010-01-01 00:00:00',
  ENGINE=InnoDB,
  DEFAULT CHARSET=utf8mb4,
  COLLATE=utf8mb4_unicode_ci;

-- Override values are tri-state:
--   1 = force on/open until expiration
--   0 = automatic control / no active override
--  -1 = force off/closed until expiration

INSERT INTO `overrides` (`id`, `windowoverride`, `windowexpire`, `fanoverride`, `fanexpire`) VALUES
  (1, 0, '2010-01-01 00:00:00', 0, '2010-01-01 00:00:00')
ON DUPLICATE KEY UPDATE
  `id` = VALUES(`id`);

ALTER TABLE `settings`
  MODIFY `id` INT(11) NOT NULL,
  MODIFY `hightemp` DECIMAL(10,2) NOT NULL,
  MODIFY `lowtemp` DECIMAL(10,2) NOT NULL,
  MODIFY `hightemprange` DECIMAL(10,2) NOT NULL,
  MODIFY `lowtemprange` DECIMAL(10,2) NOT NULL,
  MODIFY `windowtemp` DECIMAL(10,2) NOT NULL,
  MODIFY `windowtemprange` DECIMAL(10,2) NOT NULL,
  MODIFY `starttime` TIME NOT NULL,
  MODIFY `endtime` TIME NOT NULL,
  MODIFY `circfan` TINYINT(1) NOT NULL DEFAULT 0,
  ENGINE=InnoDB,
  DEFAULT CHARSET=utf8mb4,
  COLLATE=utf8mb4_unicode_ci;

CALL drop_index_if_exists('settings', 'id');
CALL drop_index_if_exists('settings', 'id_2');
CALL add_index_if_missing(
  'settings',
  'idx_settings_endtime',
  'INDEX `idx_settings_endtime` (`endtime`)'
);

INSERT INTO `settings`
  (`id`, `hightemp`, `lowtemp`, `hightemprange`, `lowtemprange`, `windowtemp`, `windowtemprange`, `starttime`, `endtime`, `circfan`)
VALUES
  (1, 40.00, 2.00, 4.00, 2.00, 39.00, 5.00, '00:00:00', '08:00:59', 1),
  (2, 40.00, 2.00, 4.00, 2.00, 39.00, 6.00, '08:01:00', '16:00:59', 0),
  (3, 40.00, 2.00, 4.00, 2.00, 39.00, 6.00, '16:01:00', '20:00:59', 1),
  (4, 40.00, 2.00, 4.00, 2.00, 39.00, 5.00, '20:01:00', '23:59:59', 1)
ON DUPLICATE KEY UPDATE
  `id` = VALUES(`id`);

UPDATE `status`
SET `timestamp` = '2010-01-01 00:00:00'
WHERE `timestamp` = '0000-00-00 00:00:00';

ALTER TABLE `status`
  MODIFY `id` INT(11) NOT NULL,
  MODIFY `heater` TINYINT(1) NOT NULL DEFAULT 0,
  MODIFY `fan` TINYINT(1) NOT NULL DEFAULT 0,
  MODIFY `circfan` TINYINT(1) NOT NULL DEFAULT 0,
  MODIFY `window` TINYINT(1) NOT NULL DEFAULT 0,
  MODIFY `timestamp` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  ENGINE=InnoDB,
  DEFAULT CHARSET=utf8mb4,
  COLLATE=utf8mb4_unicode_ci;

CALL drop_index_if_exists('status', 'id');

INSERT INTO `status` (`id`, `heater`, `fan`, `circfan`, `window`, `timestamp`) VALUES
  (1, 0, 0, 0, 0, '2010-01-01 00:00:00')
ON DUPLICATE KEY UPDATE
  `id` = VALUES(`id`);

-- ---------------------------------------------------------------------------
-- Optional default sensor profiles. These can be tuned later.
-- ---------------------------------------------------------------------------

INSERT INTO `sensor_profile`
  (`sensor_name`, `sensor_type`, `expected_min`, `expected_max`, `normal_variance`,
   `drift_sensitivity`, `noise_tolerance`, `crc_sensitivity`, `last_updated`)
VALUES
  ('BackTemp', 'indoor', -10, 50, 1.0, 1.0, 1.0, 1.0, NOW()),
  ('FrontTemp', 'indoor', -10, 50, 1.0, 1.0, 1.0, 1.0, NOW()),
  ('PiTemp', 'indoor', -10, 80, 1.0, 1.0, 1.0, 1.0, NOW()),
  ('OutsideTemp', 'outdoor', -40, 50, 2.0, 1.5, 1.5, 1.0, NOW()),
  ('WoodstoveTemp', 'equipment', -10, 120, 4.0, 2.0, 2.0, 1.0, NOW()),
  ('AverageInsideTemp', 'derived', -10, 50, 1.0, 1.0, 1.0, 1.0, NOW())
ON DUPLICATE KEY UPDATE
  `sensor_name` = VALUES(`sensor_name`);

-- ---------------------------------------------------------------------------
-- Runtime SQL user for the Python scripts.
--
-- Change this password before running in production. This user intentionally
-- has only data access permissions; use root/admin for schema migrations.
-- ---------------------------------------------------------------------------

CREATE USER IF NOT EXISTS 'greenhouse_app'@'localhost'
  IDENTIFIED BY 'change_this_password';

CREATE USER IF NOT EXISTS 'greenhouse_app'@'127.0.0.1'
  IDENTIFIED BY 'change_this_password';

GRANT SELECT, INSERT, UPDATE, DELETE
  ON `greenhouse`.*
  TO 'greenhouse_app'@'localhost';

GRANT SELECT, INSERT, UPDATE, DELETE
  ON `greenhouse`.*
  TO 'greenhouse_app'@'127.0.0.1';

FLUSH PRIVILEGES;

DROP PROCEDURE `add_index_if_missing`;
DROP PROCEDURE `drop_index_if_exists`;

COMMIT;
