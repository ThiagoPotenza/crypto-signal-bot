#!/bin/bash

echo "🚀 CRYPTO SIGNAL BOT - Monitor"
echo "=============================="

while true; do
    clear
    echo "🚀 CRYPTO SIGNAL BOT - Monitor $(date)"
    echo "=============================="
    
    echo "📊 CONTAINERS:"
    docker-compose ps
    
    echo ""
    echo "📈 DADOS POSTGRESQL:"
    docker exec -it postgres-market-data psql -U postgres -d market_data -c "SELECT COUNT(*) as total_klines FROM klines;" 2>/dev/null || echo "❌ PostgreSQL indisponível"
    
    echo ""
    echo "🔴 REDIS:"
    docker exec -it redis-market-data redis-cli INFO keyspace 2>/dev/null || echo "❌ Redis indisponível"
    
    echo ""
    echo "📊 ÚLTIMOS LOGS:"
    docker-compose logs --tail 3 market-data-service 2>/dev/null
    
    echo ""
    echo "⏰ Próxima atualização em 30s... (Ctrl+C para sair)"
    sleep 30
done
