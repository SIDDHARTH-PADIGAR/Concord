CREATE TABLE IF NOT EXISTS break_events (
    break_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    instrument_type TEXT NOT NULL,
    status TEXT NOT NULL,
    difference NUMERIC NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (break_id, status, detected_at)
);

SELECT create_hypertable('break_events', 'detected_at', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_break_events_latest
    ON break_events (symbol, instrument_type, detected_at DESC);