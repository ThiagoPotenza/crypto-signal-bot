from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
from app.services.data_processor import MarketDataProcessor
from app.config import settings

# Instância global do processor
market_processor = MarketDataProcessor()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerenciar ciclo de vida da aplicação"""
    print("🚀 Iniciando Market Data Service...")

    # Inicializar e iniciar coleta de dados
    await market_processor.initialize()
    await market_processor.start_data_collection()

    yield

    # Cleanup
    print("🛑 Parando Market Data Service...")
    await market_processor.close()

# Criar aplicação FastAPI
app = FastAPI(
    title="Market Data Service",
    description="Serviço de coleta e distribuição de dados de mercado da Binance",
    version="1.0.0",
    lifespan=lifespan
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Endpoint raiz"""
    return {
        "service": "Market Data Service",
        "status": "running",
        "version": "1.0.0",
        "is_collecting": market_processor.is_running
    }

@app.get("/health")
async def health_check():
    """Verificação de saúde"""
    try:
        status = market_processor.get_status()
        return {
            "status": "healthy",
            "processor": status,
            "symbols": settings.MONITORED_PAIRS,
            "intervals": settings.KLINE_INTERVALS
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@app.get("/status")
async def get_status():
    """Status detalhado do sistema"""
    try:
        return market_processor.get_status()
    except Exception as e:
        return {"error": str(e)}

@app.get("/latest/{symbol}")
async def get_latest_data(symbol: str):
    """Obter últimos dados de um símbolo"""
    try:
        # Buscar último ticker
        ticker_data = await market_processor.get_latest_ticker(symbol.upper())
        
        if ticker_data:
            return {
                "symbol": symbol.upper(),
                "ticker": ticker_data,
                "timestamp": ticker_data.get("timestamp") if ticker_data else None
            }
        else:
            return {
                "symbol": symbol.upper(),
                "error": "Dados não encontrados",
                "message": "Aguarde alguns minutos para os dados chegarem"
            }
    except Exception as e:
        return {
            "symbol": symbol.upper(),
            "error": str(e)
        }

@app.get("/klines/{symbol}/{interval}")
async def get_klines(symbol: str, interval: str):
    """Obter dados de klines"""
    try:
        data = await market_processor.get_latest_data(symbol.upper(), interval)
        
        if data:
            return {
                "symbol": symbol.upper(),
                "interval": interval,
                "data": data
            }
        else:
            return {
                "symbol": symbol.upper(),
                "interval": interval,
                "error": "Dados não encontrados"
            }
    except Exception as e:
        return {
            "symbol": symbol.upper(),
            "interval": interval,
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
