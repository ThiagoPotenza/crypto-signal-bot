-- Inicialização do banco de dados market_data
-- Criado automaticamente pelo Docker

-- Criar extensões necessárias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Criar schema para dados de mercado
CREATE SCHEMA IF NOT EXISTS market_data;

-- Tabela para dados de candlestick
CREATE TABLE IF NOT EXISTS market_data.klines (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    market VARCHAR(20) NOT NULL DEFAULT 'futures',
    interval VARCHAR(10) NOT NULL,
    open_time BIGINT NOT NULL,
    close_time BIGINT NOT NULL,
    open_price DECIMAL(20,8) NOT NULL,
    high_price DECIMAL(20,8) NOT NULL,
    low_price DECIMAL(20,8) NOT NULL,
    close_price DECIMAL(20,8) NOT NULL,
    volume DECIMAL(20,8) NOT NULL,
    quote_volume DECIMAL(20,8) NOT NULL,
    trades_count INTEGER NOT NULL,
    taker_buy_base_volume DECIMAL(20,8) NOT NULL,
    taker_buy_quote_volume DECIMAL(20,8) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para performance
CREATE UNIQUE INDEX IF NOT EXISTS idx_klines_unique 
ON market_data.klines (symbol, market, interval, open_time);

CREATE INDEX IF NOT EXISTS idx_klines_symbol_interval 
ON market_data.klines (symbol, interval);

CREATE INDEX IF NOT EXISTS idx_klines_open_time 
ON market_data.klines (open_time);

CREATE INDEX IF NOT EXISTS idx_klines_market 
ON market_data.klines (market);

-- Tabela para símbolos ativos
CREATE TABLE IF NOT EXISTS market_data.symbols (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    market VARCHAR(20) NOT NULL,
    base_asset VARCHAR(10) NOT NULL,
    quote_asset VARCHAR(10) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'TRADING',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_symbols_unique 
ON market_data.symbols (symbol, market);

-- Tabela para métricas do sistema
CREATE TABLE IF NOT EXISTS market_data.system_metrics (
    id SERIAL PRIMARY KEY,
    metric_name VARCHAR(50) NOT NULL,
    metric_value DECIMAL(20,8) NOT NULL,
    metric_unit VARCHAR(20),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_metrics_name_time 
ON market_data.system_metrics (metric_name, timestamp);

-- Função para atualizar updated_at automaticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers para atualizar updated_at
CREATE TRIGGER update_klines_updated_at 
    BEFORE UPDATE ON market_data.klines 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_symbols_updated_at 
    BEFORE UPDATE ON market_data.symbols 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Inserir dados iniciais
INSERT INTO market_data.symbols (symbol, market, base_asset, quote_asset) 
VALUES 
    ('BTCUSDT', 'futures', 'BTC', 'USDT'),
    ('ETHUSDT', 'futures', 'ETH', 'USDT'),
    ('BNBUSDT', 'futures', 'BNB', 'USDT')
ON CONFLICT (symbol, market) DO NOTHING;

-- Log de inicialização
INSERT INTO market_data.system_metrics (metric_name, metric_value, metric_unit) 
VALUES ('database_initialized', 1, 'boolean');
