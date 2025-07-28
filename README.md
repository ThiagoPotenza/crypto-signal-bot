# Crypto Signal Bot

Bot Trader Autônomo para Binance com capacidades de Machine Learning e análise de mercado em tempo real.

## Arquitetura

Este projeto utiliza uma arquitetura de microserviços com os seguintes componentes:

- **Market Data Service**: Coleta e distribui dados de mercado da Binance
- **Trading Engine**: Executa estratégias de trading
- **Risk Manager**: Gerencia riscos e limites
- **Notification Service**: Envia alertas multicanal
- **Dashboard**: Interface web para monitoramento

## Tecnologias

- **Backend**: Python 3.11+, FastAPI, Redis
- **Containerização**: Docker, Docker Compose
- **APIs**: Binance API, Telegram Bot API
- **Machine Learning**: TensorFlow, Scikit-learn
- **Frontend**: Next.js, TypeScript

## Configuração Rápida

1. Clone o repositório
2. Configure as variáveis de ambiente
3. Execute: `docker-compose up --build`

## Status do Projeto

🚧 **Em Desenvolvimento** - Market Data Service implementado

## Licença

Proprietary - Todos os direitos reservados
