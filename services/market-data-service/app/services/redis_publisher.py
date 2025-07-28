"""
Redis Publisher para Market Data
Publica dados em tempo real via Redis Pub/Sub
Versão 3.0 - Sistema completo e funcional
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, List
import redis.asyncio as redis
from loguru import logger
from app.config import settings


class RedisPublisher:
    """Publisher Redis para dados de mercado em tempo real"""
    
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        self.is_connected = False
        self.published_count = 0
        self.error_count = 0
        self.start_time = time.time()
        
        # Configurações de cache
        self.cache_ttl = {
            'ticker': 60,        # 1 minuto
            'kline': 300,        # 5 minutos
            'mark_price': 300,   # 5 minutos
            'orderbook': 30,     # 30 segundos
            'trades': 120        # 2 minutos
        }
        
        # Estatísticas por tipo
        self.stats = {
            'ticker': {'published': 0, 'errors': 0},
            'kline': {'published': 0, 'errors': 0},
            'mark_price': {'published': 0, 'errors': 0},
            'orderbook': {'published': 0, 'errors': 0},
            'trades': {'published': 0, 'errors': 0}
        }

    async def initialize(self):
        """Inicializar conexão Redis"""
        try:
            # Configurar conexão Redis
            redis_url = getattr(settings, 'REDIS_URL', 'redis://redis:6379')
            
            self.redis = redis.from_url(
                redis_url,
                encoding='utf-8',
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Testar conexão
            await self.redis.ping()
            self.is_connected = True
            
            logger.info(f"✅ Redis Publisher conectado: {redis_url}")
            
            # Iniciar limpeza periódica
            asyncio.create_task(self._periodic_cleanup())
            
        except Exception as e:
            logger.error(f"❌ Erro ao conectar Redis: {e}")
            self.is_connected = False
            raise

    async def publish_kline_data(self, data: Dict[str, Any]):
        """Publicar dados de candlestick"""
        try:
            if not self.is_connected:
                return
            
            # Canal específico para kline
            channel = f"kline:{data['market']}:{data['symbol']}:{data['interval']}"
            
            # Preparar mensagem
            message = {
                'type': 'kline',
                'symbol': data['symbol'],
                'market': data['market'],
                'interval': data['interval'],
                'open_time': data['open_time'],
                'close_time': data['close_time'],
                'open_price': data['open_price'],
                'high_price': data['high_price'],
                'low_price': data['low_price'],
                'close_price': data['close_price'],
                'volume': data['volume'],
                'quote_volume': data.get('quote_volume', 0),
                'trades_count': data.get('trades_count', 0),
                'taker_buy_base_volume': data.get('taker_buy_base_volume', 0),
                'taker_buy_quote_volume': data.get('taker_buy_quote_volume', 0),
                'timestamp': data['timestamp'],
                'published_at': int(time.time() * 1000)
            }
            
            # Publicar no canal
            await self.redis.publish(channel, json.dumps(message))
            
            # Cache para consultas
            cache_key = f"latest_kline:{data['market']}:{data['symbol']}:{data['interval']}"
            await self.redis.setex(cache_key, self.cache_ttl['kline'], json.dumps(message))
            
            # Atualizar estatísticas
            self.stats['kline']['published'] += 1
            self.published_count += 1
            
            # Log periódico
            if self.published_count % 5000 == 0:
                logger.info(f"📊 Redis: {self.published_count:,} mensagens publicadas")
                
        except Exception as e:
            logger.error(f"❌ Erro ao publicar kline: {e}")
            self.stats['kline']['errors'] += 1
            self.error_count += 1

    async def publish_ticker_data(self, data: Dict[str, Any]):
        """Publicar dados de ticker"""
        try:
            if not self.is_connected:
                return
            
            # Canal específico para ticker
            channel = f"ticker:{data['market']}:{data['symbol']}"
            
            # Preparar mensagem
            message = {
                'type': 'ticker',
                'symbol': data['symbol'],
                'market': data['market'],
                'price': data['price'],
                'price_change': data.get('price_change', 0),
                'price_change_percent': data.get('price_change_percent', 0),
                'volume': data.get('volume', 0),
                'quote_volume': data.get('quote_volume', 0),
                'high_price': data.get('high_price', 0),
                'low_price': data.get('low_price', 0),
                'open_price': data.get('open_price', 0),
                'weighted_avg_price': data.get('weighted_avg_price', data.get('price', 0)),
                'prev_close_price': data.get('prev_close_price', 0),
                'bid_price': data.get('bid_price', 0),
                'ask_price': data.get('ask_price', 0),
                'timestamp': data['timestamp'],
                'published_at': int(time.time() * 1000)
            }
            
            # Publicar no canal
            await self.redis.publish(channel, json.dumps(message))
            
            # Cache para consultas rápidas
            cache_key = f"latest_ticker:{data['market']}:{data['symbol']}"
            await self.redis.setex(cache_key, self.cache_ttl['ticker'], json.dumps(message))
            
            # Cache geral de preços
            price_key = f"price:{data['market']}:{data['symbol']}"
            await self.redis.setex(price_key, self.cache_ttl['ticker'], str(data['price']))
            
            # Atualizar estatísticas
            self.stats['ticker']['published'] += 1
            self.published_count += 1
            
        except Exception as e:
            logger.error(f"❌ Erro ao publicar ticker: {e}")
            self.stats['ticker']['errors'] += 1
            self.error_count += 1

    async def publish_mark_price_data(self, data: Dict[str, Any]):
        """Publicar dados de mark price (futures)"""
        try:
            if not self.is_connected:
                return
            
            # Canal específico para mark price
            channel = f"mark_price:{data['market']}:{data['symbol']}"
            
            # Preparar mensagem
            message = {
                'type': 'mark_price',
                'symbol': data['symbol'],
                'market': data['market'],
                'mark_price': data['mark_price'],
                'index_price': data.get('index_price', 0),
                'funding_rate': data.get('funding_rate', 0),
                'next_funding_time': data.get('next_funding_time', 0),
                'timestamp': data['timestamp'],
                'published_at': int(time.time() * 1000)
            }
            
            # Publicar no canal
            await self.redis.publish(channel, json.dumps(message))
            
            # Cache para consultas
            cache_key = f"latest_mark_price:{data['market']}:{data['symbol']}"
            await self.redis.setex(cache_key, self.cache_ttl['mark_price'], json.dumps(message))
            
            # Atualizar estatísticas
            self.stats['mark_price']['published'] += 1
            self.published_count += 1
            
        except Exception as e:
            logger.error(f"❌ Erro ao publicar mark price: {e}")
            self.stats['mark_price']['errors'] += 1
            self.error_count += 1

    async def publish_orderbook_data(self, data: Dict[str, Any]):
        """Publicar dados de orderbook"""
        try:
            if not self.is_connected:
                return
            
            # Canal específico para orderbook
            channel = f"orderbook:{data['market']}:{data['symbol']}"
            
            # Preparar mensagem
            message = {
                'type': 'orderbook',
                'symbol': data['symbol'],
                'market': data['market'],
                'bids': data.get('bids', []),
                'asks': data.get('asks', []),
                'timestamp': data['timestamp'],
                'published_at': int(time.time() * 1000)
            }
            
            # Publicar no canal
            await self.redis.publish(channel, json.dumps(message))
            
            # Cache para consultas
            cache_key = f"latest_orderbook:{data['market']}:{data['symbol']}"
            await self.redis.setex(cache_key, self.cache_ttl['orderbook'], json.dumps(message))
            
            # Atualizar estatísticas
            self.stats['orderbook']['published'] += 1
            self.published_count += 1
            
        except Exception as e:
            logger.error(f"❌ Erro ao publicar orderbook: {e}")
            self.stats['orderbook']['errors'] += 1
            self.error_count += 1

    async def publish_trades_data(self, data: Dict[str, Any]):
        """Publicar dados de trades"""
        try:
            if not self.is_connected:
                return
            
            # Canal específico para trades
            channel = f"trades:{data['market']}:{data['symbol']}"
            
            # Preparar mensagem
            message = {
                'type': 'trades',
                'symbol': data['symbol'],
                'market': data['market'],
                'trade_id': data.get('trade_id'),
                'price': data['price'],
                'quantity': data.get('quantity', 0),
                'is_buyer_maker': data.get('is_buyer_maker', False),
                'timestamp': data['timestamp'],
                'published_at': int(time.time() * 1000)
            }
            
            # Publicar no canal
            await self.redis.publish(channel, json.dumps(message))
            
            # Cache últimos trades
            cache_key = f"latest_trades:{data['market']}:{data['symbol']}"
            await self.redis.lpush(cache_key, json.dumps(message))
            await self.redis.ltrim(cache_key, 0, 99)  # Manter últimos 100
            await self.redis.expire(cache_key, self.cache_ttl['trades'])
            
            # Atualizar estatísticas
            self.stats['trades']['published'] += 1
            self.published_count += 1
            
        except Exception as e:
            logger.error(f"❌ Erro ao publicar trades: {e}")
            self.stats['trades']['errors'] += 1
            self.error_count += 1

    async def publish_system_status(self, status: Dict[str, Any]):
        """Publicar status do sistema"""
        try:
            if not self.is_connected:
                return
            
            # Canal de status do sistema
            channel = "system:status"
            
            # Adicionar informações do Redis
            status['redis'] = {
                'published_count': self.published_count,
                'error_count': self.error_count,
                'uptime_seconds': time.time() - self.start_time,
                'stats': self.stats
            }
            
            # Publicar status
            await self.redis.publish(channel, json.dumps(status))
            
            # Cache status
            await self.redis.setex("system:latest_status", 60, json.dumps(status))
            
        except Exception as e:
            logger.error(f"❌ Erro ao publicar status: {e}")

    async def get_latest_data(self, data_type: str, market: str, symbol: str) -> Optional[Dict]:
        """Obter últimos dados de um tipo específico"""
        try:
            if not self.is_connected:
                return None
            
            cache_key = f"latest_{data_type}:{market}:{symbol}"
            data = await self.redis.get(cache_key)
            
            if data:
                return json.loads(data)
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter dados: {e}")
            return None

    async def get_price(self, market: str, symbol: str) -> Optional[float]:
        """Obter preço atual de um símbolo"""
        try:
            if not self.is_connected:
                return None
            
            price_key = f"price:{market}:{symbol}"
            price = await self.redis.get(price_key)
            
            if price:
                return float(price)
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter preço: {e}")
            return None

    async def get_symbols_list(self, market: str) -> List[str]:
        """Obter lista de símbolos ativos de um mercado"""
        try:
            if not self.is_connected:
                return []
            
            # Buscar chaves de preços
            pattern = f"price:{market}:*"
            keys = []
            
            cursor = 0
            while True:
                cursor, batch = await self.redis.scan(cursor, match=pattern, count=1000)
                keys.extend(batch)
                if cursor == 0:
                    break
            
            # Extrair símbolos
            symbols = []
            for key in keys:
                parts = key.split(':')
                if len(parts) >= 3:
                    symbols.append(parts[2])
            
            return sorted(list(set(symbols)))
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter símbolos: {e}")
            return []

    async def cleanup_old_data(self):
        """Limpar dados antigos do Redis"""
        try:
            if not self.is_connected:
                return
            
            logger.info("🧹 Limpando dados antigos do Redis...")
            
            # Padrões de chaves para limpar
            patterns = [
                "latest_*",
                "price:*",
                "system:*"
            ]
            
            total_cleaned = 0
            
            for pattern in patterns:
                cursor = 0
                while True:
                    cursor, keys = await self.redis.scan(cursor, match=pattern, count=1000)
                    
                    for key in keys:
                        try:
                            ttl = await self.redis.ttl(key)
                            if ttl == -1:  # Sem TTL
                                # Definir TTL baseado no tipo
                                if "latest_ticker" in key or "price:" in key:
                                    await self.redis.expire(key, self.cache_ttl['ticker'])
                                elif "latest_kline" in key:
                                    await self.redis.expire(key, self.cache_ttl['kline'])
                                elif "latest_mark_price" in key:
                                    await self.redis.expire(key, self.cache_ttl['mark_price'])
                                else:
                                    await self.redis.expire(key, 3600)  # 1 hora padrão
                                
                                total_cleaned += 1
                        except:
                            continue
                    
                    if cursor == 0:
                        break
            
            logger.info(f"✅ {total_cleaned} chaves configuradas com TTL")
            
        except Exception as e:
            logger.error(f"❌ Erro na limpeza: {e}")

    async def _periodic_cleanup(self):
        """Limpeza periódica automática"""
        while self.is_connected:
            try:
                # Aguardar 30 minutos
                await asyncio.sleep(1800)
                
                # Executar limpeza
                await self.cleanup_old_data()
                
                # Log estatísticas
                uptime = time.time() - self.start_time
                logger.info(f"📊 Redis Stats: {self.published_count:,} publicadas, {self.error_count} erros, {uptime:.0f}s uptime")
                
            except Exception as e:
                logger.error(f"❌ Erro na limpeza periódica: {e}")
                await asyncio.sleep(300)  # Tentar novamente em 5 min

    def get_status(self) -> Dict[str, Any]:
        """Obter status do Redis Publisher"""
        uptime = time.time() - self.start_time
        
        return {
            'is_connected': self.is_connected,
            'published_count': self.published_count,
            'error_count': self.error_count,
            'uptime_seconds': uptime,
            'stats_by_type': self.stats,
            'cache_ttl_config': self.cache_ttl
        }

    async def stop(self):
        """Parar o Redis Publisher"""
        try:
            logger.info("🛑 Parando Redis Publisher...")
            self.is_connected = False
            
            if self.redis:
                await self.redis.close()
            
            logger.success("✅ Redis Publisher parado")
            
        except Exception as e:
            logger.error(f"❌ Erro ao parar Redis: {e}")

# Instância global
redis_publisher = RedisPublisher()
