#!/bin/bash

# Docker entrypoint script for stratum proxy
# Handles conditional argument passing based on environment variables

ARGS=(
    "python" "-m" "rxd_proxy.main"
    "--ip=0.0.0.0"
    "--port=${STRATUM_PORT:-54321}"
    "--rpcip=radiant"
    "--rpcport=${RXD_RPC_PORT:-7332}"
    "--rpcuser=${RXD_RPC_USER}"
    "--rpcpass=${RXD_RPC_PASS}"
)

# Add conditional arguments
if [ -n "${PROXY_SIGNATURE}" ]; then
    ARGS+=("--proxy-signature=${PROXY_SIGNATURE}")
fi

# Add log level if specified (takes precedence over VERBOSE)
if [ -n "${LOG_LEVEL}" ]; then
    ARGS+=("--log-level=${LOG_LEVEL}")
fi

# Add conditional flags only if they are explicitly set to "true"
if [ "${TESTNET,,}" = "true" ]; then
    ARGS+=("--testnet")
fi

if [ "${VERBOSE,,}" = "true" ]; then
    ARGS+=("--verbose")
fi

if [ "${SHOW_JOBS,,}" = "true" ]; then
    ARGS+=("--jobs")
fi

if [ "${USE_EASIER_TARGET,,}" = "true" ]; then
    ARGS+=("--use-easier-target")
fi

# ZMQ arguments
if [ "${ENABLE_ZMQ,,}" = "true" ]; then
    ARGS+=("--enable-zmq")
    if [ -n "${RXD_ZMQ_ENDPOINT}" ]; then
        ARGS+=("--rxd-zmq-endpoint=${RXD_ZMQ_ENDPOINT}")
    fi
elif [ "${ENABLE_ZMQ,,}" = "false" ]; then
    ARGS+=("--disable-zmq")
fi

echo "Starting with arguments: ${ARGS[@]}"
exec "${ARGS[@]}"