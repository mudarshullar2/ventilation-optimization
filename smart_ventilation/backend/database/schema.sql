-- Home air-quality monitoring schema.
-- One row per sensor reading, keyed by room so the app is multi-room from day one.

CREATE TABLE IF NOT EXISTS readings (
    id          BIGSERIAL PRIMARY KEY,
    ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
    room        TEXT        NOT NULL,
    co2         DOUBLE PRECISION,
    pm25        DOUBLE PRECISION,
    voc         DOUBLE PRECISION,
    temperature DOUBLE PRECISION,
    humidity    DOUBLE PRECISION
);

-- Fast "latest per room" and per-room history queries.
CREATE INDEX IF NOT EXISTS idx_readings_room_ts ON readings (room, ts DESC);

-- AI insights: one row per room per worker run (forecast, anomaly flags, NL summary).
CREATE TABLE IF NOT EXISTS insights (
    id           BIGSERIAL PRIMARY KEY,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    room         TEXT        NOT NULL,
    forecast     JSONB,
    anomalies    JSONB,
    summary      TEXT
);
CREATE INDEX IF NOT EXISTS idx_insights_room_ts ON insights (room, generated_at DESC);

-- Radiator (TRV) state over time: current temp, requested target, valve opening.
CREATE TABLE IF NOT EXISTS radiator_state (
    id           BIGSERIAL PRIMARY KEY,
    ts           TIMESTAMPTZ NOT NULL DEFAULT now(),
    room         TEXT        NOT NULL,
    current_temp DOUBLE PRECISION,
    target_temp  DOUBLE PRECISION,
    valve        DOUBLE PRECISION,
    mode         TEXT
);
CREATE INDEX IF NOT EXISTS idx_radiator_room_ts ON radiator_state (room, ts DESC);
