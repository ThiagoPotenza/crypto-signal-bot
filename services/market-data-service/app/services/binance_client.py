"""
Cliente Binance Multi-Market com WebSocket Real
Versão 5.0 - CONEXÕES REAIS E FUNCIONAIS
Suporte completo para SPOT, FUTURES, COIN-M e OPTIONS
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Any
import aiohttp
import websockets
from loguru import logger
from app.config import BINANCE_APIS, MARKET_CONFIG, get_websocket_url

class BinanceClient:
    """Cliente Binance com WebSocket real e coleta otimizada"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.data_processor = None
        self.active_connections: List[asyncio.Task] = []
        self.connection_status: Dict[str, bool] = {}
        self.message_count: int = 0
        self.error_count: int = 0
        self.start_time: float = time.time()
        self.is_running: bool = False
        self.reconnect_attempts: Dict[str, int] = {}
        self.max_reconnect_attempts: int = 5
        self.reconnect_delay: int = 5
        
        # Estatísticas por mercado
        self.market_stats: Dict[str, Dict] = {}
        
        # Configurações de WebSocket
        self.ws_config = {
            'ping_interval': 20,
            'ping_timeout': 10,
            'close_timeout': 10,
            'max_size': 10**6,  # 1MB
            'max_queue': 32
        }

    async def initialize(self):
        """Inicializar cliente com sessão HTTP"""
        try:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                connector=aiohttp.TCPConnector(limit=100, limit_per_host=30)
            )
            
            # Inicializar estatísticas
            for market in BINANCE_APIS.keys():
                self.market_stats[market] = {
                    'messages': 0,
                    'errors': 0,
                    'last_message': None,
                    'connected': False,
                    'symbols': 0
                }
                self.connection_status[market] = False
                self.reconnect_attempts[market] = 0
            
            logger.info("🚀 Cliente Binance Multi-Market inicializado")
            logger.info("📊 Mercados suportados: SPOT, USD-M, COIN-M, OPTIONS")
            
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar cliente: {e}")
            raise

    async def start_market_streams(self, market_symbols: Dict[str, List[str]]):
        """Iniciar streams WebSocket para todos os mercados"""
        try:
            logger.info("🎯 Iniciando streams para todos os mercados...")
            self.is_running = True
            
            # Iniciar streams por mercado
            for market, symbols in market_symbols.items():
                if not symbols:
                    logger.warning(f"⚠️ Nenhum símbolo para {market}")
                    continue
                
                if not MARKET_CONFIG.get(market, {}).get('enabled', False):
                    logger.info(f"📴 Mercado {market} desabilitado")
                    continue
                
                logger.info(f"🔄 Iniciando {market.upper()}: {len(symbols)} símbolos")
                
                # Atualizar estatísticas
                self.market_stats[market]['symbols'] = len(symbols)
                
                # Iniciar streams específicos por mercado
                if market == 'spot':
                    await self._start_spot_streams(symbols)
                elif market == 'futures':
                    await self._start_futures_streams(symbols)
                elif market == 'coin_futures':
                    await self._start_coin_futures_streams(symbols)
                elif market == 'options':
                    await self._start_options_streams(symbols)
                
                # Pequena pausa entre mercados
                await asyncio.sleep(1)
            
            logger.success("🎉 Todos os streams iniciados com sucesso!")
            
            # Iniciar monitoramento
            asyncio.create_task(self._monitor_connections())
            
        except Exception as e:
            logger.error(f"❌ Erro ao iniciar streams: {e}")
            raise

    async def _start_spot_streams(self, symbols: List[str]):
        """Iniciar streams WebSocket para SPOT"""
        try:
            logger.info(f"📈 Iniciando {len(symbols)} streams SPOT...")
            
            # Dividir em lotes de 50 símbolos (limite da Binance)
            batch_size = 50
            batches = [symbols[i:i + batch_size] for i in range(0, len(symbols), batch_size)]
            
            for batch_idx, batch in enumerate(batches):
                # Criar streams para este lote
                streams = []
                for symbol in batch:
                    symbol_lower = symbol.lower()
                    streams.extend([
                        f"{symbol_lower}@kline_1m",
                        f"{symbol_lower}@kline_5m",
                        f"{symbol_lower}@ticker"
                    ])
                
                # URL do WebSocket
                ws_url = f"wss://stream.binance.com:9443/stream?streams={'/'.join(streams)}"
                
                # Criar conexão
                connection_id = f"spot_batch_{batch_idx}"
                task = asyncio.create_task(
                    self._handle_websocket_connection(
                        ws_url, 'spot', batch, connection_id
                    )
                )
                self.active_connections.append(task)
                
                logger.info(f"  ✅ Lote {batch_idx + 1}/{len(batches)}: {len(batch)} símbolos")
                await asyncio.sleep(0.2)  # Evitar rate limit
            
            self.connection_status['spot'] = True
            logger.success(f"🎉 SPOT: {len(symbols)} símbolos em {len(batches)} conexões")
            
        except Exception as e:
            logger.error(f"❌ Erro streams SPOT: {e}")
            self.connection_status['spot'] = False

    async def _start_futures_streams(self, symbols: List[str]):
        """Iniciar streams WebSocket para FUTURES"""
        try:
            logger.info(f"🔮 Iniciando {len(symbols)} streams FUTURES...")
            
            batch_size = 50
            batches = [symbols[i:i + batch_size] for i in range(0, len(symbols), batch_size)]
            
            for batch_idx, batch in enumerate(batches):
                streams = []
                for symbol in batch:
                    symbol_lower = symbol.lower()
                    streams.extend([
                        f"{symbol_lower}@kline_1m",
                        f"{symbol_lower}@kline_5m",
                        f"{symbol_lower}@ticker",
                        f"{symbol_lower}@markPrice"
                    ])
                
                ws_url = f"wss://fstream.binance.com/stream?streams={'/'.join(streams)}"
                
                connection_id = f"futures_batch_{batch_idx}"
                task = asyncio.create_task(
                    self._handle_websocket_connection(
                        ws_url, 'futures', batch, connection_id
                    )
                )
                self.active_connections.append(task)
                
                logger.info(f"  ✅ Lote {batch_idx + 1}/{len(batches)}: {len(batch)} símbolos")
                await asyncio.sleep(0.2)
            
            self.connection_status['futures'] = True
            logger.success(f"🎉 FUTURES: {len(symbols)} símbolos em {len(batches)} conexões")
            
        except Exception as e:
            logger.error(f"❌ Erro streams FUTURES: {e}")
            self.connection_status['futures'] = False

    async def _start_coin_futures_streams(self, symbols: List[str]):
        """Iniciar streams WebSocket para COIN-M FUTURES"""
        try:
            logger.info(f"🪙 Iniciando {len(symbols)} streams COIN-M...")
            
            batch_size = 30  # Menor para COIN-M
            batches = [symbols[i:i + batch_size] for i in range(0, len(symbols), batch_size)]
            
            for batch_idx, batch in enumerate(batches):
                streams = []
                for symbol in batch:
                    symbol_lower = symbol.lower()
                    streams.extend([
                        f"{symbol_lower}@kline_1m",
                        f"{symbol_lower}@kline_5m",
                        f"{symbol_lower}@ticker"
                    ])
                
                ws_url = f"wss://dstream.binance.com/stream?streams={'/'.join(streams)}"
                
                connection_id = f"coin_futures_batch_{batch_idx}"
                task = asyncio.create_task(
                    self._handle_websocket_connection(
                        ws_url, 'coin_futures', batch, connection_id
                    )
                )
                self.active_connections.append(task)
                
                logger.info(f"  ✅ Lote {batch_idx + 1}/{len(batches)}: {len(batch)} símbolos")
                await asyncio.sleep(0.3)
            
            self.connection_status['coin_futures'] = True
            logger.success(f"🎉 COIN-M: {len(symbols)} símbolos em {len(batches)} conexões")
            
        except Exception as e:
            logger.error(f"❌ Erro streams COIN-M: {e}")
            self.connection_status['coin_futures'] = False

    async def _start_options_streams(self, symbols: List[str]):
        """Iniciar streams WebSocket para OPTIONS"""
        try:
            logger.info(f"⚡ Iniciando {len(symbols)} streams OPTIONS...")
            
            # OPTIONS tem limitações diferentes
            batch_size = 20
            batches = [symbols[i:i + batch_size] for i in range(0, len(symbols), batch_size)]
            
            for batch_idx, batch in enumerate(batches):
                streams = []
                for symbol in batch:
                    symbol_lower = symbol.lower()
                    streams.append(f"{symbol_lower}@ticker")
                
                ws_url = f"wss://nbstream.binance.com/eoptions/stream?streams={'/'.join(streams)}"
                
                connection_id = f"options_batch_{batch_idx}"
                task = asyncio.create_task(
                    self._handle_websocket_connection(
                        ws_url, 'options', batch, connection_id
                    )
                )
                self.active_connections.append(task)
                
                logger.info(f"  ✅ Lote {batch_idx + 1}/{len(batches)}: {len(batch)} símbolos")
                await asyncio.sleep(0.5)
            
            self.connection_status['options'] = True
            logger.success(f"🎉 OPTIONS: {len(symbols)} símbolos em {len(batches)} conexões")
            
        except Exception as e:
            logger.error(f"❌ Erro streams OPTIONS: {e}")
            self.connection_status['options'] = False

    async def _handle_websocket_connection(self, ws_url: str, market: str, symbols: List[str], connection_id: str):
        """Gerenciar conexão WebSocket individual com reconexão automática"""
        while self.is_running and self.reconnect_attempts[market] < self.max_reconnect_attempts:
            try:
                logger.info(f"🔌 Conectando {connection_id}: {len(symbols)} símbolos")
                
                async with websockets.connect(
                    ws_url,
                    ping_interval=self.ws_config['ping_interval'],
                    ping_timeout=self.ws_config['ping_timeout'],
                    close_timeout=self.ws_config['close_timeout'],
                    max_size=self.ws_config['max_size'],
                    max_queue=self.ws_config['max_queue']
                ) as websocket:
                    
                    logger.success(f"✅ {connection_id} CONECTADO!")
                    self.market_stats[market]['connected'] = True
                    self.reconnect_attempts[market] = 0  # Reset contador
                    
                    # Loop principal de recebimento
                    async for message in websocket:
                        try:
                            await self._process_websocket_message(message, market, connection_id)
                            
                        except json.JSONDecodeError:
                            logger.warning(f"⚠️ JSON inválido em {connection_id}")
                            self.market_stats[market]['errors'] += 1
                            
                        except Exception as e:
                            logger.error(f"❌ Erro processando mensagem {connection_id}: {e}")
                            self.market_stats[market]['errors'] += 1
                            
            except websockets.exceptions.ConnectionClosed:
                logger.warning(f"🔌 Conexão {connection_id} fechada")
                self.market_stats[market]['connected'] = False
                
            except Exception as e:
                logger.error(f"❌ Erro conexão {connection_id}: {e}")
                self.market_stats[market]['connected'] = False
                self.market_stats[market]['errors'] += 1
            
            # Tentar reconectar
            if self.is_running:
                self.reconnect_attempts[market] += 1
                delay = self.reconnect_delay * self.reconnect_attempts[market]
                logger.info(f"🔄 Reconectando {connection_id} em {delay}s (tentativa {self.reconnect_attempts[market]})")
                await asyncio.sleep(delay)
        
        logger.error(f"❌ {connection_id} esgotou tentativas de reconexão")

    async def _process_websocket_message(self, message: str, market: str, connection_id: str):
        """Processar mensagem WebSocket recebida"""
        try:
            data = json.loads(message)
            
            # Verificar se é mensagem de stream
            if 'stream' in data and 'data' in data:
                stream_name = data['stream']
                stream_data = data['data']
                
                # Extrair símbolo
                symbol = stream_name.split('@')[0].upper()
                
                # Processar por tipo de stream
                if '@kline_' in stream_name:
                    await self._process_kline_data(stream_data, market, symbol, stream_name)
                elif '@ticker' in stream_name:
                    await self._process_ticker_data(stream_data, market, symbol)
                elif '@markPrice' in stream_name:
                    await self._process_mark_price_data(stream_data, market, symbol)
                
                # Atualizar estatísticas
                self.message_count += 1
                self.market_stats[market]['messages'] += 1
                self.market_stats[market]['last_message'] = time.time()
                
                # Log periódico
                if self.message_count % 5000 == 0:
                    logger.info(f"📊 Total: {self.message_count:,} mensagens processadas")
                    
        except Exception as e:
            logger.error(f"❌ Erro processando mensagem: {e}")
            self.error_count += 1

    async def _process_kline_data(self, data: dict, market: str, symbol: str, stream_name: str):
        """Processar dados de candlestick"""
        try:
            kline = data.get('k', {})
            
            # Só processar candlesticks fechados
            if kline.get('x'):  # x = true significa fechado
                interval = kline.get('i')
                
                processed_data = {
                    'symbol': symbol,
                    'market': market,
                    'interval': interval,
                    'open_time': int(kline.get('t', 0)),
                    'close_time': int(kline.get('T', 0)),
                    'open_price': float(kline.get('o', 0)),
                    'high_price': float(kline.get('h', 0)),
                    'low_price': float(kline.get('l', 0)),
                    'close_price': float(kline.get('c', 0)),
                    'volume': float(kline.get('v', 0)),
                    'quote_volume': float(kline.get('q', 0)),
                    'trades_count': int(kline.get('n', 0)),
                    'taker_buy_base_volume': float(kline.get('V', 0)),
                    'taker_buy_quote_volume': float(kline.get('Q', 0)),
                    'timestamp': int(kline.get('T', 0))
                }
                
                # Enviar para processamento se temos processor
                if self.data_processor:
                    await self.data_processor.process_kline_data(processed_data)
                
                # Log ocasional
                if self.message_count % 1000 == 0:
                    logger.debug(f"📈 {symbol} {interval}: {processed_data['close_price']}")
                    
        except Exception as e:
            logger.error(f"❌ Erro kline {symbol}: {e}")

    async def _process_ticker_data(self, data: dict, market: str, symbol: str):
        """Processar dados de ticker"""
        try:
            processed_data = {
                'symbol': symbol,
                'market': market,
                'price': float(data.get('c', 0)),
                'price_change': float(data.get('P', 0)),
                'price_change_percent': float(data.get('p', 0)),
                'volume': float(data.get('v', 0)),
                'quote_volume': float(data.get('q', 0)),
                'high_price': float(data.get('h', 0)),
                'low_price': float(data.get('l', 0)),
                'open_price': float(data.get('o', 0)),
                'timestamp': int(data.get('E', 0))
            }
            
            # Enviar para processamento
            if self.data_processor:
                await self.data_processor.process_ticker_data(processed_data)
                
        except Exception as e:
            logger.error(f"❌ Erro ticker {symbol}: {e}")

    async def _process_mark_price_data(self, data: dict, market: str, symbol: str):
        """Processar dados de mark price (futures)"""
        try:
            processed_data = {
                'symbol': symbol,
                'market': market,
                'mark_price': float(data.get('p', 0)),
                'index_price': float(data.get('i', 0)),
                'funding_rate': float(data.get('r', 0)),
                'next_funding_time': int(data.get('T', 0)),
                'timestamp': int(data.get('E', 0))
            }
            
            # Enviar para processamento
            if self.data_processor:
                await self.data_processor.process_mark_price_data(processed_data)
                
        except Exception as e:
            logger.error(f"❌ Erro mark price {symbol}: {e}")

    async def _monitor_connections(self):
        """Monitorar status das conexões"""
        while self.is_running:
            try:
                # Verificar conexões ativas
                active_count = len([task for task in self.active_connections if not task.done()])
                total_messages = sum(stats['messages'] for stats in self.market_stats.values())
                total_errors = sum(stats['errors'] for stats in self.market_stats.values())
                uptime = time.time() - self.start_time
                
                logger.info(f"🔄 Conexões: {active_count}, Msgs: {total_messages:,}, Erros: {total_errors}, Uptime: {uptime:.0f}s")
                
                # Status por mercado
                for market, stats in self.market_stats.items():
                    if stats['symbols'] > 0:
                        status = "🟢" if stats['connected'] else "🔴"
                        logger.info(f"  {status} {market.upper()}: {stats['messages']:,} msgs, {stats['errors']} erros")
                
                await asyncio.sleep(30)  # Monitor a cada 30s
                
            except Exception as e:
                logger.error(f"❌ Erro no monitor: {e}")
                await asyncio.sleep(10)

    def get_status(self) -> Dict[str, Any]:
        """Obter status completo do cliente"""
        uptime = time.time() - self.start_time
        active_connections = len([task for task in self.active_connections if not task.done()])
        
        return {
            'is_running': self.is_running,
            'uptime_seconds': uptime,
            'active_connections': active_connections,
            'total_messages': self.message_count,
            'total_errors': self.error_count,
            'markets': self.market_stats,
            'connection_status': self.connection_status
        }

    async def stop(self):
        """Parar todas as conexões"""
        try:
            logger.info("🛑 Parando cliente Binance...")
            self.is_running = False
            
            # Cancelar todas as tasks
            for task in self.active_connections:
                if not task.done():
                    task.cancel()
            
            # Aguardar cancelamento
            if self.active_connections:
                await asyncio.gather(*self.active_connections, return_exceptions=True)
            
            # Fechar sessão HTTP
            if self.session:
                await self.session.close()
            
            logger.success("✅ Cliente Binance parado")
            
        except Exception as e:
            logger.error(f"❌ Erro ao parar cliente: {e}")

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

# Instância global
binance_client = BinanceClient()
