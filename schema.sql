-- Marketmind PostgreSQL schema

CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    mode VARCHAR(5) NOT NULL DEFAULT 'paper',
    symbol VARCHAR(10) NOT NULL,
    direction VARCHAR(10),
    qty INTEGER,
    entry_price NUMERIC(12,4),
    entry_time TIMESTAMPTZ,
    stop_loss NUMERIC(12,4),
    take_profit NUMERIC(12,4),
    score NUMERIC(6,2),
    grok_rationale TEXT,
    score_breakdown JSONB,
    status VARCHAR(20) DEFAULT 'open',
    exit_price NUMERIC(12,4),
    exit_time TIMESTAMPTZ,
    pnl NUMERIC(12,4),
    asset_type VARCHAR(10) DEFAULT 'stock',
    option_details JSONB,
    sector VARCHAR(50),
    atr_at_entry NUMERIC(12,4),
    trailing_stop_updates INTEGER DEFAULT 0,
    scale_out_level INTEGER DEFAULT 0,
    hold_duration_hours NUMERIC(10,2),
    strategy_tag VARCHAR(30)
);
CREATE INDEX IF NOT EXISTS idx_trades_mode_status ON trades(mode, status);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);

CREATE TABLE IF NOT EXISTS daily_snapshots (
    id SERIAL PRIMARY KEY,
    mode VARCHAR(5) NOT NULL DEFAULT 'paper',
    date DATE NOT NULL,
    equity NUMERIC(12,2),
    cash NUMERIC(12,2),
    positions_value NUMERIC(12,2),
    open_positions INTEGER,
    day_pnl NUMERIC(12,4),
    cumulative_pnl NUMERIC(12,4),
    spy_close NUMERIC(12,4),
    btcusd_close NUMERIC(12,4),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(mode, date)
);

CREATE TABLE IF NOT EXISTS rejected_signals (
    id SERIAL PRIMARY KEY,
    mode VARCHAR(5) NOT NULL DEFAULT 'paper',
    symbol VARCHAR(10),
    direction VARCHAR(10),
    score NUMERIC(6,2),
    reason TEXT,
    score_breakdown JSONB,
    sector VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS api_usage (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    requests INTEGER DEFAULT 0,
    input_tokens BIGINT DEFAULT 0,
    output_tokens BIGINT DEFAULT 0,
    total_cost NUMERIC(10,4) DEFAULT 0,
    signals_generated INTEGER DEFAULT 0,
    UNIQUE(date)
);

CREATE TABLE IF NOT EXISTS symbol_cache (
    symbol VARCHAR(10) PRIMARY KEY,
    name VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS options_positions (
    id SERIAL PRIMARY KEY,
    mode VARCHAR(5) NOT NULL DEFAULT 'paper',
    key VARCHAR(50) NOT NULL,
    strategy VARCHAR(30),
    underlying VARCHAR(10),
    contracts JSONB,
    entry_time TIMESTAMPTZ,
    net_debit_credit NUMERIC(12,4),
    max_loss NUMERIC(12,4),
    max_profit NUMERIC(12,4),
    score NUMERIC(6,2),
    profit_target_pct NUMERIC(6,4),
    stop_loss_pct NUMERIC(6,4),
    dte_exit INTEGER DEFAULT 2,
    entry_underlying_price NUMERIC(12,4),
    status VARCHAR(20) DEFAULT 'open',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_options_mode_status ON options_positions(mode, status);

CREATE TABLE IF NOT EXISTS daily_stats (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    starting_equity NUMERIC(12,2),
    UNIQUE(date)
);

CREATE TABLE IF NOT EXISTS config_overrides (
    key VARCHAR(50) PRIMARY KEY,
    value JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_target (
    id INTEGER PRIMARY KEY DEFAULT 1,
    target NUMERIC(12,2),
    CHECK (id = 1)
);

CREATE TABLE IF NOT EXISTS congress_cache (
    id SERIAL PRIMARY KEY,
    data JSONB NOT NULL,
    fetched_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bot_instances (
    id SERIAL PRIMARY KEY,
    pid INTEGER NOT NULL,
    hostname VARCHAR(100),
    started_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alpaca_keys (
    id INTEGER PRIMARY KEY DEFAULT 1,
    mode VARCHAR(5) NOT NULL DEFAULT 'paper',
    api_key VARCHAR(100) NOT NULL,
    secret_key VARCHAR(100) NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CHECK (id = 1)
);

CREATE TABLE IF NOT EXISTS logs (
    id SERIAL PRIMARY KEY,
    mode VARCHAR(5) NOT NULL DEFAULT 'paper',
    level VARCHAR(10),
    logger_name VARCHAR(100),
    message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_logs_created ON logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_logs_mode ON logs(mode);

-- Migrations (safe to re-run, handles existing DBs)
ALTER TABLE trades ADD COLUMN IF NOT EXISTS hold_duration_hours NUMERIC(10,2);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS strategy_tag VARCHAR(30);
