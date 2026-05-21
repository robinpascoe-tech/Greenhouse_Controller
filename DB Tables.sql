CREATE TABLE sensor_health (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sensor_name VARCHAR(64),
    timestamp DATETIME,

    health_score INT,
    status VARCHAR(32),

    crc_rate DECIMAL(6,3),
    variance DECIMAL(10,4),

    drift_short DECIMAL(10,4),
    drift_long DECIMAL(10,4),

    confidence DECIMAL(5,2),
    notes TEXT
);

CREATE TABLE sensor_alerts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sensor_name VARCHAR(64),
    timestamp DATETIME,
    alert_type VARCHAR(32),
    message TEXT
);

CREATE TABLE sensor_state (
    sensor_name VARCHAR(64) PRIMARY KEY,

    last_status VARCHAR(32),
    last_health INT,

    ema_health DECIMAL(6,2),
    ema_variance DECIMAL(10,4),

    last_change_time DATETIME
);

CREATE TABLE sensor_profile (
    sensor_name VARCHAR(64) PRIMARY KEY,

    sensor_type VARCHAR(32),

    -- expected behavior ranges
    expected_min FLOAT,
    expected_max FLOAT,
    normal_variance FLOAT,

    -- sensitivity tuning
    drift_sensitivity FLOAT DEFAULT 1.0,
    noise_tolerance FLOAT DEFAULT 1.0,
    crc_sensitivity FLOAT DEFAULT 1.0,

    -- adaptive learning
    learned_mean FLOAT,
    learned_variance FLOAT,

    last_updated DATETIME
);