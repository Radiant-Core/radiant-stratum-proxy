#!/bin/bash

# Radiant Stratum Proxy Setup Script

set -e

echo "🚀 Setting up Radiant Stratum Proxy..."

# Check if Docker and Docker Compose are installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Function to generate random password
generate_password() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-25
}

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    
    # Generate secure password
    RXD_PASS=$(generate_password)
    
    cat > .env << EOF
# Radiant Node Configuration
RXD_RPC_USER=radiant_user
RXD_RPC_PASS=${RXD_PASS}
RXD_RPC_PORT=7332
RXD_P2P_PORT=7333
RXD_ZMQ_PORT=29332
RXD_ZMQ_RAW_PORT=29333

# Stratum Proxy Configuration
STRATUM_PORT=54321
TESTNET=false
LOG_LEVEL=INFO
SHOW_JOBS=false
USE_EASIER_TARGET=true

# ZMQ Configuration
ENABLE_ZMQ=true
RXD_ZMQ_ENDPOINT=tcp://radiant:29332

# Dashboard Configuration
ENABLE_DASHBOARD=true
DASHBOARD_PORT=8080

# Database Configuration (for historical data)
ENABLE_DATABASE=true

# Variable Difficulty (optional)
ENABLE_VARDIFF=false
VARDIFF_TARGET_SHARE_TIME=15.0
VARDIFF_MIN_DIFFICULTY=0.00001
VARDIFF_MAX_DIFFICULTY=0.1

# Notifications (optional - fill in to enable)
# DISCORD_WEBHOOK_URL=
# TELEGRAM_BOT_TOKEN=
# TELEGRAM_CHAT_ID=
EOF

    echo "✅ .env file created with random password"
else
    echo "✅ .env file already exists"
fi

# Create data directories
mkdir -p submit_history data

echo "✅ Data directories created"

# Check binaries
echo "🔍 Checking binaries..."
if [ -f ./check-binaries.sh ]; then
    ./check-binaries.sh
fi

# Build and start services
echo "🔨 Building and starting services..."
docker compose build --no-cache
docker compose up -d

echo ""
echo "🎉 Setup complete!"
echo ""
echo "📊 Service Status:"
docker compose ps

echo ""
echo "📝 Next Steps:"
echo "1. Wait for blockchain sync (check with: docker compose logs -f radiant)"
echo "2. Connect your miner to localhost:54321"
echo "3. View dashboard at http://localhost:8080"
echo ""
echo "📖 Commands:"
echo "  View logs:     docker compose logs -f"
echo "  Stop services: docker compose down"
echo "  Restart:       docker compose restart"
echo ""
echo "🔧 Monitoring:"
echo "  RXD status:   docker compose exec radiant radiant-cli getblockchaininfo"
echo "  Proxy logs:   docker compose logs -f stratum-proxy"
