#!/bin/bash

# Health check script for Radiant node
# This runs as root but switches to radiant user to run the CLI command
# Explicitly specify connection details to ensure we use the right port

if su radiant -c "radiant-cli -rpcconnect=127.0.0.1 -rpcport=${RXD_RPC_PORT:-7332} getblockchaininfo" > /dev/null 2>&1; then
    exit 0
else
    exit 1
fi