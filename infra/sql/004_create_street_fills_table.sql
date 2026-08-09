CREATE TABLE IF NOT EXISTS street_fills (
    exchange_execution_id TEXT NOT NULL,
    trade_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    instrument_type TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity NUMERIC NOT NULL,
    price NUMERIC NOT NULL,
    executed_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    corrects_execution_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (exchange_execution_id, executed_at)
);

SELECT create_hypertable('street_fills', 'executed_at', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_street_fills_trade_id ON street_fills (trade_id);