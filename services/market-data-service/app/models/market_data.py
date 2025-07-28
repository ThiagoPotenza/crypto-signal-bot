"""
Modelos de dados para informações de mercado
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class DataType(str, Enum):
    """Tipos de dados de mercado"""
    KLINE = "kline"
    TICKER = "ticker"
    DEPTH = "depth"
    TRADE = "trade"


class MarketData(BaseModel):
    """Modelo para dados de kline/candlestick"""
    
    symbol: str = Field(..., description="Símbolo do par de trading (ex: BTCUSDT)")
    interval: str = Field(..., description="Intervalo do kline (ex: 1m, 5m, 1h)")
    open_time: int = Field(..., description="Timestamp de abertura")
    close_time: int = Field(..., description="Timestamp de fechamento")
    open_price: float = Field(..., description="Preço de abertura")
    high_price: float = Field(..., description="Preço máximo")
    low_price: float = Field(..., description="Preço mínimo")
    close_price: float = Field(..., description="Preço de fechamento")
    volume: float = Field(..., description="Volume negociado")
    number_of_trades: int = Field(..., description="Número de trades")
    is_closed: bool = Field(..., description="Se o kline está fechado")
    
    class Config:
        """Configuração do modelo"""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    @property
    def open_datetime(self) -> datetime:
        """Retorna datetime de abertura"""
        return datetime.fromtimestamp(self.open_time / 1000)
    
    @property
    def close_datetime(self) -> datetime:
        """Retorna datetime de fechamento"""
        return datetime.fromtimestamp(self.close_time / 1000)
    
    @property
    def price_change(self) -> float:
        """Retorna mudança de preço"""
        return self.close_price - self.open_price
    
    @property
    def price_change_percent(self) -> float:
        """Retorna mudança de preço em percentual"""
        if self.open_price == 0:
            return 0.0
        return ((self.close_price - self.open_price) / self.open_price) * 100
    
    def to_dict(self) -> dict:
        """Converte para dicionário"""
        return {
            "symbol": self.symbol,
            "interval": self.interval,
            "open_time": self.open_time,
            "close_time": self.close_time,
            "open_price": self.open_price,
            "high_price": self.high_price,
            "low_price": self.low_price,
            "close_price": self.close_price,
            "volume": self.volume,
            "number_of_trades": self.number_of_trades,
            "is_closed": self.is_closed,
            "price_change": self.price_change,
            "price_change_percent": self.price_change_percent
        }


class TickerData(BaseModel):
    """Modelo para dados de ticker"""
    
    symbol: str = Field(..., description="Símbolo do par de trading")
    price: float = Field(..., description="Preço atual")
    change: float = Field(..., description="Mudança percentual 24h")
    volume: float = Field(..., description="Volume 24h")
    timestamp: int = Field(..., description="Timestamp dos dados")
    
    @property
    def datetime(self) -> datetime:
        """Retorna datetime dos dados"""
        return datetime.fromtimestamp(self.timestamp / 1000)
    
    def to_dict(self) -> dict:
        """Converte para dicionário"""
        return {
            "symbol": self.symbol,
            "price": self.price,
            "change": self.change,
            "volume": self.volume,
            "timestamp": self.timestamp
        }


class MarketDataMessage(BaseModel):
    """Modelo para mensagens de dados de mercado"""
    
    data_type: DataType
    symbol: str
    timestamp: datetime
    data: Dict[str, Any]
    source: str = "binance"

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class KlineData(BaseModel):
    """Modelo para dados de kline (compatibilidade)"""
    
    symbol: str
    interval: str
    open_time: datetime
    close_time: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    quote_volume: float
    trades_count: int
    taker_buy_base_volume: float
    taker_buy_quote_volume: float


class MarketSummary(BaseModel):
    """Modelo para resumo de mercado"""
    
    symbol: str = Field(..., description="Símbolo do par")
    current_price: float = Field(..., description="Preço atual")
    change_24h: float = Field(..., description="Mudança 24h")
    volume_24h: float = Field(..., description="Volume 24h")
    high_24h: float = Field(..., description="Máxima 24h")
    low_24h: float = Field(..., description="Mínima 24h")
    last_update: int = Field(..., description="Última atualização")
    
    @property
    def last_update_datetime(self) -> datetime:
        """Retorna datetime da última atualização"""
        return datetime.fromtimestamp(self.last_update / 1000)
    
    def to_dict(self) -> dict:
        """Converte para dicionário"""
        return {
            "symbol": self.symbol,
            "current_price": self.current_price,
            "change_24h": self.change_24h,
            "volume_24h": self.volume_24h,
            "high_24h": self.high_24h,
            "low_24h": self.low_24h,
            "last_update": self.last_update
        }
