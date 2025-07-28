"""
Configuração de logging para o Market Data Service
"""

import sys
from loguru import logger
from app.config import settings


def setup_logger():
    """Configura o logger da aplicação"""
    
    # Remover logger padrão
    logger.remove()
    
    # Adicionar logger para console
    logger.add(
        sys.stdout,
        format=settings.LOG_FORMAT,
        level=settings.LOG_LEVEL,
        colorize=True
    )
    
    # Adicionar logger para arquivo
    logger.add(
        "logs/market_data_service.log",
        format=settings.LOG_FORMAT,
        level=settings.LOG_LEVEL,
        rotation="1 day",
        retention="7 days",
        compression="zip"
    )
    
    return logger


def get_logger():
    """Retorna o logger configurado"""
    return logger
