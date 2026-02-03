#!/bin/bash

# Health check script for the Radiant mining setup

set -e

echo "🔍 Checking Radiant Stratum Proxy Health..."
echo "============================================"

# Function to check service status
check_service() {
    local service=$1
    local status=$(docker compose ps -q $service 2>/dev/null)
    
    if [ -z "$status" ]; then
        echo "❌ $service: Not running"
        return 1
    else
        local health=$(docker inspect --format='{{.State.Health.Status}}' $(docker compose ps -q $service) 2>/dev/null || echo "no-health-check")
        if [ "$health" = "healthy" ]; then
            echo "✅ $service: Running and healthy"
        elif [ "$health" = "unhealthy" ]; then
            echo "⚠️  $service: Running but unhealthy"
        else
            echo "🟡 $service: Running (no health check)"
        fi
    fi
}

# Check Docker Compose services
echo "📋 Service Status:"
check_service "radiant"
check_service "stratum-proxy"

echo ""
echo "🔗 Network Connectivity:"

# Check if services can communicate
if docker compose exec -T stratum-proxy python -c "import socket; s=socket.socket(); s.settimeout(5); s.connect(('radiant', 7332)); s.close(); print('✅ Proxy -> Radiant RPC: OK')" 2>/dev/null; then
    :
else
    echo "❌ Proxy -> Radiant RPC: Failed"
fi

echo ""
echo "⛓️  Blockchain Status:"

# Check Radiant sync status
RXD_INFO=$(docker compose exec -T radiant radiant-cli getblockchaininfo 2>/dev/null || echo "error")
if [ "$RXD_INFO" != "error" ]; then
    RXD_BLOCKS=$(echo "$RXD_INFO" | grep -o '"blocks":[0-9]*' | cut -d: -f2)
    RXD_HEADERS=$(echo "$RXD_INFO" | grep -o '"headers":[0-9]*' | cut -d: -f2)
    if [ "$RXD_BLOCKS" = "$RXD_HEADERS" ]; then
        echo "✅ Radiant: Synced ($RXD_BLOCKS blocks)"
    else
        echo "🔄 Radiant: Syncing ($RXD_BLOCKS/$RXD_HEADERS blocks)"
    fi
else
    echo "❌ Radiant: RPC Error"
fi

echo ""
echo "🎯 Stratum Proxy:"

# Check if stratum port is accessible
if nc -z localhost 54321 2>/dev/null; then
    echo "✅ Stratum port 54321: Accessible"
else
    echo "❌ Stratum port 54321: Not accessible"
fi

echo ""
echo "📊 Recent Activity:"
echo "Last 5 proxy log entries:"
docker compose logs --tail=5 stratum-proxy 2>/dev/null || echo "No recent logs available"

echo ""
echo "💡 Troubleshooting:"
echo "  Full logs:        docker compose logs -f"
echo "  Radiant logs:     docker compose logs -f radiant"
echo "  Proxy logs:       docker compose logs -f stratum-proxy"
