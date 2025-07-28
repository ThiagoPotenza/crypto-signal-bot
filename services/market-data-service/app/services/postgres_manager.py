"""
PostgreSQL Manager para Market Data
Gerencia conexões e operações com PostgreSQL
Versão 4.0 - Sistema completo e funcional
"""

import asyncio
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import asyncpg
from loguru import logger
from app.config import settings


class PostgresManager:
    """Gerenciador PostgreSQL para dados de mercado"""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.is_connected = False
        self.saved_count = 0
        self.error_count = 0
        self.start_time = time.time()
        
        # Estatísticas por tipo
        self.stats = {
            'klines': {'saved': 0, 'errors': 0},
            'tickers': {'saved': 0, 'errors': 0},
            'mark_prices': {'saved': 0, 'errors': 0},
            'trades': {'saved': 0, 'errors': 0}
        }
        
        # Configurações de batch
        self.batch_size = 5000
        self.batch_timeout = 30
        self.pending_batches = {
            'klines': [],
            'tickers': [],
            'mark_prices': [],
            'trades': []
        }

    async def initialize(self):
        """Inicializar conexão com PostgreSQL"""
        try:
            logger.info("🐘 Inicializando conexão com PostgreSQL...")
            
            # Configurar string de conexão
            db_url = getattr(settings, 'DATABASE_URL', 
                           'postgresql://postgres:postgres@postgres:5432/crypto_signals')
            
            # Criar pool de conexões
            self.pool = await asyncpg.create_pool(
                db_url,
                min_size=5,
                max_size=20,
                command_timeout=30,
                server_settings={
                    'jit': 'off',
                    'application_name': 'market_data_service'
                }
            )
            
            # Testar conexão
            async with self.pool.acquire() as conn:
                await conn.execute('SELECT 1')
            
            self.is_connected = True
            
            # Criar tabelas
            await self._create_tables()
            
            # Iniciar processamento em batch
            asyncio.create_task(self._batch_processor())
            
            logger.success("✅ PostgreSQL conectado e tabelas criadas")
            
        except Exception as e:
            logger.error(f"❌ Erro ao conectar PostgreSQL: {e}")
            self.is_connected = False
            raise

    async def _create_tables(self):
        """Criar tabelas necessárias"""
        try:
            async with self.pool.acquire() as conn:
                # Tabela de klines (candlesticks)
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS klines (
                        id BIGSERIAL PRIMARY KEY,
                        symbol VARCHAR(20) NOT NULL,
                        market VARCHAR(20) NOT NULL,
                        interval VARCHAR(10) NOT NULL,
                        open_time BIGINT NOT NULL,
                        close_time BIGINT NOT NULL,
                        open_price DECIMAL(20,8) NOT NULL,
                        high_price DECIMAL(20,8) NOT NULL,
                        low_price DECIMAL(20,8) NOT NULL,
                        close_price DECIMAL(20,8) NOT NULL,
                        volume DECIMAL(20,8) NOT NULL DEFAULT 0,
                        quote_volume DECIMAL(20,8) NOT NULL DEFAULT 0,
                        trades_count INTEGER NOT NULL DEFAULT 0,
                        taker_buy_base_volume DECIMAL(20,8) NOT NULL DEFAULT 0,
                        taker_buy_quote_volume DECIMAL(20,8) NOT NULL DEFAULT 0,
                        is_closed BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        UNIQUE(symbol, market, interval, open_time)
                    )
                """)
                
                # Tabela de tickers
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS tickers (
                        id BIGSERIAL PRIMARY KEY,
                        symbol VARCHAR(20) NOT NULL,
                        market VARCHAR(20) NOT NULL,
                        price DECIMAL(20,8) NOT NULL,
                        price_change DECIMAL(20,8) NOT NULL DEFAULT 0,
                        price_change_percent DECIMAL(10,4) NOT NULL DEFAULT 0,
                        volume DECIMAL(20,8) NOT NULL DEFAULT 0,
                        quote_volume DECIMAL(20,8) NOT NULL DEFAULT 0,
                        high_price DECIMAL(20,8) NOT NULL DEFAULT 0,
                        low_price DECIMAL(20,8) NOT NULL DEFAULT 0,
                        open_price DECIMAL(20,8) NOT NULL DEFAULT 0,
                        weighted_avg_price DECIMAL(20,8) NOT NULL DEFAULT 0,
                        prev_close_price DECIMAL(20,8) NOT NULL DEFAULT 0,
                        bid_price DECIMAL(20,8) NOT NULL DEFAULT 0,
                        ask_price DECIMAL(20,8) NOT NULL DEFAULT 0,
                        timestamp BIGINT NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        UNIQUE(symbol, market, timestamp)
                    )
                """)
                
                # Tabela de mark prices (futures)
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS mark_prices (
                        id BIGSERIAL PRIMARY KEY,
                        symbol VARCHAR(20) NOT NULL,
                        market VARCHAR(20) NOT NULL,
                        mark_price DECIMAL(20,8) NOT NULL,
                        index_price DECIMAL(20,8) NOT NULL DEFAULT 0,
                        funding_rate DECIMAL(10,8) NOT NULL DEFAULT 0,
                        next_funding_time BIGINT NOT NULL DEFAULT 0,
                        timestamp BIGINT NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        UNIQUE(symbol, market, timestamp)
                    )
                """)
                
                # Tabela de trades
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS trades (
                        id BIGSERIAL PRIMARY KEY,
                        symbol VARCHAR(20) NOT NULL,
                        market VARCHAR(20) NOT NULL,
                        trade_id BIGINT,
                        price DECIMAL(20,8) NOT NULL,
                        quantity DECIMAL(20,8) NOT NULL DEFAULT 0,
                        is_buyer_maker BOOLEAN NOT NULL DEFAULT FALSE,
                        timestamp BIGINT NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """)
                
                # Índices para performance
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_klines_symbol_market_interval_time 
                    ON klines(symbol, market, interval, open_time DESC)
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_tickers_symbol_market_timestamp 
                    ON tickers(symbol, market, timestamp DESC)
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_mark_prices_symbol_market_timestamp 
                    ON mark_prices(symbol, market, timestamp DESC)
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_trades_symbol_market_timestamp 
                    ON trades(symbol, market, timestamp DESC)
                """)
                
                # Índices para limpeza de dados antigos
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_klines_created_at 
                    ON klines(created_at)
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_tickers_created_at 
                    ON tickers(created_at)
                """)
                
            logger.info("📊 Tabelas PostgreSQL criadas/verificadas")
            
        except Exception as e:
            logger.error(f"❌ Erro ao criar tabelas: {e}")
            raise

    async def save_kline_data(self, data: Dict[str, Any]):
        """Salvar dados de kline no PostgreSQL"""
        try:
            if not self.is_connected:
                return
            
            # Validar dados obrigatórios
            required_fields = ['symbol', 'market', 'interval', 'open_time', 'close_time',
                             'open_price', 'high_price', 'low_price', 'close_price', 'volume']
            
            for field in required_fields:
                if field not in data:
                    logger.warning(f"⚠️ Campo obrigatório ausente em kline: {field}")
                    return
            
            # Preparar dados com valores padrão seguros
            kline_data = {
                'symbol': str(data['symbol']),
                'market': str(data['market']),
                'interval': str(data['interval']),
                'open_time': int(data['open_time']),
                'close_time': int(data['close_time']),
                'open_price': float(data['open_price']),
                'high_price': float(data['high_price']),
                'low_price': float(data['low_price']),
                'close_price': float(data['close_price']),
                'volume': float(data['volume']),
                'quote_volume': float(data.get('quote_volume', 0)),
                'trades_count': int(data.get('trades_count', 0)),
                'taker_buy_base_volume': float(data.get('taker_buy_base_volume', 0)),
                'taker_buy_quote_volume': float(data.get('taker_buy_quote_volume', 0)),
                'is_closed': True,  # Sempre True para dados processados
                'created_at': datetime.utcnow()
            }
            
            # Adicionar ao batch
            self.pending_batches['klines'].append(kline_data)
            
            # Processar batch se atingiu o limite
            if len(self.pending_batches['klines']) >= self.batch_size:
                await self._process_klines_batch()
            
        except Exception as e:
            logger.error(f"❌ Erro ao preparar kline: {e}")
            self.stats['klines']['errors'] += 1
            self.error_count += 1

    async def save_ticker_data(self, data: Dict[str, Any]):
        """Salvar dados de ticker no PostgreSQL"""
        try:
            if not self.is_connected:
                return
            
            # Validar dados obrigatórios
            if 'symbol' not in data or 'market' not in data or 'price' not in data:
                return
            
            # Preparar dados
            ticker_data = {
                'symbol': str(data['symbol']),
                'market': str(data['market']),
                'price': float(data['price']),
                'price_change': float(data.get('price_change', 0)),
                'price_change_percent': float(data.get('price_change_percent', 0)),
                'volume': float(data.get('volume', 0)),
                'quote_volume': float(data.get('quote_volume', 0)),
                'high_price': float(data.get('high_price', 0)),
                'low_price': float(data.get('low_price', 0)),
                'open_price': float(data.get('open_price', 0)),
                'weighted_avg_price': float(data.get('weighted_avg_price', data.get('price', 0))),
                'prev_close_price': float(data.get('prev_close_price', 0)),
                'bid_price': float(data.get('bid_price', 0)),
                'ask_price': float(data.get('ask_price', 0)),
                'timestamp': int(data.get('timestamp', int(time.time() * 1000))),
                'created_at': datetime.utcnow()
            }
            
            # Adicionar ao batch
            self.pending_batches['tickers'].append(ticker_data)
            
            # Processar batch se necessário
            if len(self.pending_batches['tickers']) >= self.batch_size:
                await self._process_tickers_batch()
            
        except Exception as e:
            logger.error(f"❌ Erro ao preparar ticker: {e}")
            self.stats['tickers']['errors'] += 1
            self.error_count += 1

    async def save_mark_price_data(self, data: Dict[str, Any]):
        """Salvar dados de mark price no PostgreSQL"""
        try:
            if not self.is_connected:
                return
            
            # Validar dados obrigatórios
            if 'symbol' not in data or 'market' not in data or 'mark_price' not in data:
                return
            
            # Preparar dados
            mark_price_data = {
                'symbol': str(data['symbol']),
                'market': str(data['market']),
                'mark_price': float(data['mark_price']),
                'index_price': float(data.get('index_price', 0)),
                'funding_rate': float(data.get('funding_rate', 0)),
                'next_funding_time': int(data.get('next_funding_time', 0)),
                'timestamp': int(data.get('timestamp', int(time.time() * 1000))),
                'created_at': datetime.utcnow()
            }
            
            # Adicionar ao batch
            self.pending_batches['mark_prices'].append(mark_price_data)
            
            # Processar batch se necessário
            if len(self.pending_batches['mark_prices']) >= self.batch_size:
                await self._process_mark_prices_batch()
            
        except Exception as e:
            logger.error(f"❌ Erro ao preparar mark price: {e}")
            self.stats['mark_prices']['errors'] += 1
            self.error_count += 1

    async def _process_klines_batch(self):
        """Processar batch de klines"""
        try:
            if not self.pending_batches['klines']:
                return
            
            batch = self.pending_batches['klines'].copy()
            self.pending_batches['klines'].clear()
            
            async with self.pool.acquire() as conn:
                # Preparar query de inserção em massa
                query = """
                INSERT INTO klines (
                    symbol, market, interval, open_time, close_time,
                    open_price, high_price, low_price, close_price,
                    volume, quote_volume, trades_count,
                    taker_buy_base_volume, taker_buy_quote_volume,
                    is_closed, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                ON CONFLICT (symbol, market, interval, open_time) 
                DO UPDATE SET
                    close_time = EXCLUDED.close_time,
                    open_price = EXCLUDED.open_price,
                    high_price = EXCLUDED.high_price,
                    low_price = EXCLUDED.low_price,
                    close_price = EXCLUDED.close_price,
                    volume = EXCLUDED.volume,
                    quote_volume = EXCLUDED.quote_volume,
                    trades_count = EXCLUDED.trades_count,
                    taker_buy_base_volume = EXCLUDED.taker_buy_base_volume,
                    taker_buy_quote_volume = EXCLUDED.taker_buy_quote_volume,
                    is_closed = EXCLUDED.is_closed,
                    updated_at = NOW()
                """
                
                # Executar inserções em massa
                for item in batch:
                    values = (
                        item['symbol'], item['market'], item['interval'],
                        item['open_time'], item['close_time'],
                        item['open_price'], item['high_price'], 
                        item['low_price'], item['close_price'],
                        item['volume'], item['quote_volume'], item['trades_count'],
                        item['taker_buy_base_volume'], item['taker_buy_quote_volume'],
                        item['is_closed'], item['created_at']
                    )
                    await conn.execute(query, *values)
                
                self.stats['klines']['saved'] += len(batch)
                self.saved_count += len(batch)
                
                # Log periódico
                if self.saved_count % 1000 == 0:
                    logger.info(f"💾 PostgreSQL: {self.saved_count:,} registros salvos")
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar batch klines: {e}")
            self.stats['klines']['errors'] += len(batch)
            self.error_count += len(batch)

    async def _process_tickers_batch(self):
        """Processar batch de tickers"""
        try:
            if not self.pending_batches['tickers']:
                return
            
            batch = self.pending_batches['tickers'].copy()
            self.pending_batches['tickers'].clear()
            
            async with self.pool.acquire() as conn:
                query = """
                INSERT INTO tickers (
                    symbol, market, price, price_change, price_change_percent,
                    volume, quote_volume, high_price, low_price, open_price,
                    weighted_avg_price, prev_close_price, bid_price, ask_price,
                    timestamp, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                ON CONFLICT (symbol, market, timestamp) 
                DO UPDATE SET
                    price = EXCLUDED.price,
                    price_change = EXCLUDED.price_change,
                    price_change_percent = EXCLUDED.price_change_percent,
                    volume = EXCLUDED.volume,
                    quote_volume = EXCLUDED.quote_volume,
                    high_price = EXCLUDED.high_price,
                    low_price = EXCLUDED.low_price,
                    open_price = EXCLUDED.open_price,
                    weighted_avg_price = EXCLUDED.weighted_avg_price,
                    prev_close_price = EXCLUDED.prev_close_price,
                    bid_price = EXCLUDED.bid_price,
                    ask_price = EXCLUDED.ask_price
                """
                
                for item in batch:
                    values = (
                        item['symbol'], item['market'], item['price'],
                        item['price_change'], item['price_change_percent'],
                        item['volume'], item['quote_volume'],
                        item['high_price'], item['low_price'], item['open_price'],
                        item['weighted_avg_price'], item['prev_close_price'],
                        item['bid_price'], item['ask_price'],
                        item['timestamp'], item['created_at']
                    )
                    await conn.execute(query, *values)
                
                self.stats['tickers']['saved'] += len(batch)
                self.saved_count += len(batch)
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar batch tickers: {e}")
            self.stats['tickers']['errors'] += len(batch)

    async def _process_mark_prices_batch(self):
        """Processar batch de mark prices"""
        try:
            if not self.pending_batches['mark_prices']:
                return
            
            batch = self.pending_batches['mark_prices'].copy()
            self.pending_batches['mark_prices'].clear()
            
            async with self.pool.acquire() as conn:
                query = """
                INSERT INTO mark_prices (
                    symbol, market, mark_price, index_price, funding_rate,
                    next_funding_time, timestamp, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (symbol, market, timestamp) 
                DO UPDATE SET
                    mark_price = EXCLUDED.mark_price,
                    index_price = EXCLUDED.index_price,
                    funding_rate = EXCLUDED.funding_rate,
                    next_funding_time = EXCLUDED.next_funding_time
                """
                
                for item in batch:
                    values = (
                        item['symbol'], item['market'], item['mark_price'],
                        item['index_price'], item['funding_rate'],
                        item['next_funding_time'], item['timestamp'], item['created_at']
                    )
                    await conn.execute(query, *values)
                
                self.stats['mark_prices']['saved'] += len(batch)
                self.saved_count += len(batch)
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar batch mark prices: {e}")
            self.stats['mark_prices']['errors'] += len(batch)

    async def _batch_processor(self):
        """Processador de batches periódico"""
        while self.is_connected:
            try:
                # Aguardar timeout do batch
                await asyncio.sleep(self.batch_timeout)
                
                # Processar todos os batches pendentes
                await self._process_klines_batch()
                await self._process_tickers_batch()
                await self._process_mark_prices_batch()
                
            except Exception as e:
                logger.error(f"❌ Erro no processador de batch: {e}")
                await asyncio.sleep(5)

    async def cleanup_old_data(self, days_to_keep: int = 30):
        """Limpar dados antigos do PostgreSQL"""
        try:
            if not self.is_connected:
                return
            
            logger.info(f"🧹 Limpando dados PostgreSQL mais antigos que {days_to_keep} dias...")
            
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            async with self.pool.acquire() as conn:
                # Limpar tickers antigos (manter apenas últimos 7 dias)
                result = await conn.execute(
                    "DELETE FROM tickers WHERE created_at < $1",
                    cutoff_date - timedelta(days=23)  # Total 7 dias
                )
                logger.info(f"  🗑️ Tickers removidos: {result.split()[-1]}")
                
                # Limpar mark prices antigos (manter apenas últimos 30 dias)
                result = await conn.execute(
                    "DELETE FROM mark_prices WHERE created_at < $1",
                    cutoff_date
                )
                logger.info(f"  🗑️ Mark prices removidos: {result.split()[-1]}")
                
                # Manter klines por mais tempo (90 dias para 1m, mais para intervalos maiores)
                intervals_retention = {
                    '1m': 7,    # 7 dias
                    '5m': 30,   # 30 dias
                    '15m': 60,  # 60 dias
                    '1h': 180,  # 180 dias
                    '4h': 365,  # 1 ano
                    '1d': 1095  # 3 anos
                }
                
                for interval, retention_days in intervals_retention.items():
                    interval_cutoff = datetime.utcnow() - timedelta(days=retention_days)
                    result = await conn.execute(
                        "DELETE FROM klines WHERE interval = $1 AND created_at < $2",
                        interval, interval_cutoff
                    )
                    logger.info(f"  🗑️ Klines {interval} removidos: {result.split()[-1]}")
            
            logger.success("✅ Limpeza PostgreSQL concluída")
            
        except Exception as e:
            logger.error(f"❌ Erro na limpeza PostgreSQL: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Obter status do PostgreSQL Manager"""
        uptime = time.time() - self.start_time
        
        return {
            'is_connected': self.is_connected,
            'saved_count': self.saved_count,
            'error_count': self.error_count,
            'uptime_seconds': uptime,
            'stats_by_type': self.stats,
            'pending_batches': {k: len(v) for k, v in self.pending_batches.items()},
            'batch_config': {
                'batch_size': self.batch_size,
                'batch_timeout': self.batch_timeout
            }
        }

    async def stop(self):
        """Parar o PostgreSQL Manager"""
        try:
            logger.info("🛑 Parando PostgreSQL Manager...")
            self.is_connected = False
            
            # Processar batches pendentes
            await self._process_klines_batch()
            await self._process_tickers_batch()
            await self._process_mark_prices_batch()
            
            # Fechar pool
            if self.pool:
                await self.pool.close()
            
            logger.success("✅ PostgreSQL Manager parado")
            
        except Exception as e:
            logger.error(f"❌ Erro ao parar PostgreSQL: {e}")

# Instância global
postgres_manager = PostgresManager()
