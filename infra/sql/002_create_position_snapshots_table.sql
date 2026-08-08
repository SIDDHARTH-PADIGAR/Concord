CREATE TABLE IF NOT EXISTS position_snapshots (
    symbol TEXT NOT NULL,
    instrument_type TEXT NOT NULL,
    quantity NUMERIC NOT NULL,
    as_of TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, instrument_type, as_of)
);

SELECT create_hypertable('position_snapshots', 'as_of', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_position_snapshots_latest
    ON position_snapshots (symbol, instrument_type, as_of DESC);