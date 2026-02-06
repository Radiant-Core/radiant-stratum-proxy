#!/bin/bash
set -e

# Radiant Node Docker Entrypoint
# Generates configuration from environment variables and starts radiantd

DATA_DIR="/home/radiant/.radiant"

# Function to log with timestamp
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Radiant Node: $1"
}

# Ensure the data directory exists and has correct permissions
log "Setting up data directory..."
mkdir -p "$DATA_DIR"
chown -R radiant:radiant "$DATA_DIR"

# Create radiant.conf from environment variables
log "Generating radiant.conf..."

# Set default ports based on network
if [ "${TESTNET}" = "true" ] || [ "${TESTNET}" = "1" ]; then
    DEFAULT_RPC_PORT=17332
    DEFAULT_P2P_PORT=17333
    DEFAULT_ZMQ_PORT=39332
    DEFAULT_ZMQ_RAW_PORT=39333
    NETWORK_MODE="testnet"
    log "Using TESTNET default ports (RPC: 17332, P2P: 17333, ZMQ: 39332/39333)"
else
    DEFAULT_RPC_PORT=7332
    DEFAULT_P2P_PORT=7333
    DEFAULT_ZMQ_PORT=29332
    DEFAULT_ZMQ_RAW_PORT=29333
    NETWORK_MODE="mainnet"
fi

# Use environment variables if set, otherwise use network-appropriate defaults
RPC_PORT=${RXD_RPC_PORT:-$DEFAULT_RPC_PORT}
P2P_PORT=${RXD_P2P_PORT:-$DEFAULT_P2P_PORT}
ZMQ_PORT=${RXD_ZMQ_PORT:-$DEFAULT_ZMQ_PORT}
ZMQ_RAW_PORT=${RXD_ZMQ_RAW_PORT:-$DEFAULT_ZMQ_RAW_PORT}

# Convert boolean environment variables to 1/0 for radiant.conf
UPNP_VALUE=0
if [ "${RADIANT_UPNP}" = "true" ] || [ "${RADIANT_UPNP}" = "1" ]; then
    UPNP_VALUE=1
fi

MAX_CONN=${RADIANT_MAX_CONNECTIONS:-50}

# Build config with proper sections
if [ "$NETWORK_MODE" = "testnet" ]; then
    cat > "$DATA_DIR/radiant.conf" << EOF
# Generated from environment variables - TESTNET
testnet=1

# Global settings
server=1
listen=1
daemon=0
printtoconsole=1
maxconnections=${MAX_CONN}
timeout=30000
upnp=${UPNP_VALUE}
discover=1
dnsseed=1

# RPC credentials (global)
rpcuser=${RXD_RPC_USER}
rpcpassword=${RXD_RPC_PASS}

[test]
# Testnet-specific settings
rpcport=${RPC_PORT}
rpcallowip=0.0.0.0/0
rpcbind=0.0.0.0:${RPC_PORT}
port=${P2P_PORT}
bind=0.0.0.0:${P2P_PORT}

# ZMQ Configuration for block notifications
zmqpubhashblock=tcp://0.0.0.0:${ZMQ_PORT}
zmqpubrawblock=tcp://0.0.0.0:${ZMQ_RAW_PORT}
EOF
else
    cat > "$DATA_DIR/radiant.conf" << EOF
# Generated from environment variables - MAINNET

# Global settings
server=1
listen=1
daemon=0
printtoconsole=1
maxconnections=${MAX_CONN}
timeout=30000
upnp=${UPNP_VALUE}
discover=1
dnsseed=1

# RPC credentials (global)
rpcuser=${RXD_RPC_USER}
rpcpassword=${RXD_RPC_PASS}

[main]
# Mainnet-specific settings
rpcport=${RPC_PORT}
rpcallowip=0.0.0.0/0
rpcbind=0.0.0.0:${RPC_PORT}
port=${P2P_PORT}
bind=0.0.0.0:${P2P_PORT}

# ZMQ Configuration for block notifications
zmqpubhashblock=tcp://0.0.0.0:${ZMQ_PORT}
zmqpubrawblock=tcp://0.0.0.0:${ZMQ_RAW_PORT}
EOF
fi

# Fix ownership of the config file
chown radiant:radiant "$DATA_DIR/radiant.conf"

log "Configuration complete ($NETWORK_MODE), starting radiantd..."

# Function to handle graceful shutdown
shutdown_handler() {
    log "Received shutdown signal, stopping radiantd gracefully..."
    if [ -n "$RADIANTD_PID" ]; then
        # Use radiant-cli stop for clean shutdown (flushes chainstate to disk)
        su radiant -c "radiant-cli -rpcconnect=127.0.0.1 -rpcport=${RPC_PORT} stop" 2>/dev/null || true
        # Wait for process to exit
        wait "$RADIANTD_PID" 2>/dev/null
    fi
    log "radiantd stopped cleanly"
    exit 0
}

# Trap SIGTERM and SIGINT for graceful shutdown
trap shutdown_handler SIGTERM SIGINT

# Start radiantd as radiant user in background so we can handle signals
su radiant -c "radiantd $*" &
RADIANTD_PID=$!

log "radiantd started with PID $RADIANTD_PID"

# Wait for the process (this allows trap to work)
wait "$RADIANTD_PID"
exit_code=$?

log "radiantd exited with code $exit_code"
exit $exit_code