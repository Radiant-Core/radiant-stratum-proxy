# Radiant Stratum Proxy

A stratum mining proxy for Radiant (RXD) blockchain using SHA512/256d proof-of-work.

## Features

- ✅ **SHA512/256d Mining**: Native support for Radiant's proof-of-work algorithm
- ✅ **ZMQ Support**: Instant new block notifications
- ✅ **Notifications**: Discord and Telegram alerts for blocks found and miner connections
- ✅ **Web Dashboard** _(optional)_: Real-time monitoring of miners, hashrates, and blocks
- ✅ **SQLite Database** _(optional)_: Historical statistics and block history
- ✅ **Variable Difficulty** _(optional)_: Automatic difficulty adjustment per miner
- ✅ **Docker Ready**: Complete docker compose setup with health checks
- ✅ **Flexible Difficulty**: Configurable share difficulty for any hashrate

## Quick Start

Choose your setup method:

### Option 1: Docker Compose (Recommended)

**Prerequisites:** Docker and Docker Compose installed

The Docker setup automatically builds Radiant from source - no need to download binaries!

1. **Configure environment** (choose based on your hardware):

   **Linux/macOS:**
   ```bash
   # For ASIC miners (IceRiver, etc.) - RECOMMENDED for solo mining
   cp .env.example.asic .env

   # For GPU miners (testing/development)
   cp .env.example.gpu .env

   # Then edit .env - set a secure RPC password
   nano .env
   ```

   **Windows (PowerShell):**
   ```powershell
   # For ASIC miners (IceRiver, etc.) - RECOMMENDED for solo mining
   Copy-Item .env.example.asic .env

   # For GPU miners (testing/development)
   Copy-Item .env.example.gpu .env

   # Then edit .env - set a secure RPC password
   notepad .env
   ```

2. **Start services** (first build takes ~10-15 minutes to compile Radiant):

   ```bash
   docker compose up -d
   docker compose logs -f stratum-proxy  # Watch logs
   ```
   **Note**: First build compiles Radiant from source (https://github.com/Radiant-Core/Radiant-Core). 
   Subsequent starts are instant since the image is cached.

3. **Connect miner**:
   - Server: `localhost:54321`
   - Username: Your Radiant address
   - Password: anything

### Option 2: Native Python (Your Own Node)

**Prerequisites:** Python 3.10+, running radiantd node

1. **Configure blockchain node**:

   - Copy `config/radiant.conf` to your Radiant data directory
   - Edit with secure password
   - Start radiantd

2. **Install Python dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure proxy**:

   **Linux/macOS:**
   ```bash
   cp .env.example.gpu .env   # For GPU miners
   cp .env.example.asic .env  # For ASIC miners
   ```

   **Windows (PowerShell):**
   ```powershell
   Copy-Item .env.example.gpu .env   # For GPU miners
   Copy-Item .env.example.asic .env  # For ASIC miners
   ```

   Then edit `.env` to match your node RPC settings.

4. **Run proxy**:

   ```bash
   python -m rxd_proxy.run
   ```

5. **Connect miner**: Same as Docker method above

## Configuration

### Essential Environment Variables

| Variable                        | Description                        | Default            |
| ------------------------------- | ---------------------------------- | ------------------ |
| `RXD_RPC_PORT`                  | Radiant RPC port                   | 7332               |
| `RXD_RPC_USER` / `RXD_RPC_PASS` | Radiant RPC credentials            | -                  |
| `STRATUM_PORT`                  | Port for miners to connect         | 54321              |
| `STATIC_SHARE_DIFFICULTY`       | Share difficulty (GPU=1, ASIC=512) | 512.0              |
| `USE_EASIER_TARGET`             | Use easier target for shares       | true               |
| `ENABLE_ZMQ`                    | Enable ZMQ block notifications     | true               |
| `DISCORD_WEBHOOK_URL`           | Discord webhook for notifications  | (blank = disabled) |
| `TELEGRAM_BOT_TOKEN`            | Telegram bot token                 | (blank = disabled) |
| `TELEGRAM_CHAT_ID`              | Telegram chat ID                   | (blank = disabled) |
| `ENABLE_DASHBOARD`              | Enable web dashboard               | false              |
| `DASHBOARD_PORT`                | Web dashboard port                 | 8080               |
| `ENABLE_DATABASE`               | Enable statistics database         | false              |

See [NOTIFICATIONS.md](NOTIFICATIONS.md) for notification setup and [DASHBOARD.md](DASHBOARD.md) for dashboard configuration.

### Share Difficulty

`STATIC_SHARE_DIFFICULTY` sets the exact difficulty for shares:

- **GPU (1.0)**: Frequent shares for hashrate tracking
- **ASIC (512.0)**: Higher difficulty for IceRiver RX0 (300 GH/s)

With VarDiff enabled (recommended), this is only used as fallback.

## Radiant Mining

### How It Works

Radiant uses **SHA512/256d** (double SHA512/256) for proof-of-work:

```
Block Header (80 bytes)
    ↓
SHA512/256d hash → Compare with RXD target
    ↓
    └─→ Meets target? → Submit to RXD → Earn RXD rewards

Block Reward: 25,000 RXD (post-halving)
Block Time: ~5 minutes
```

### Block Finding

When a share meets or exceeds the network difficulty target:

1. Share submitted by miner
2. Proxy validates SHA512/256d hash
3. If hash ≤ network target → Block found!
4. Submit block to Radiant node
5. Notification sent (if configured)

## Monitoring

**Block submissions** are logged to `./submit_history/`:

- `RXD_<height>_<job>_<time>.txt` - Radiant blocks

**Check logs:**

```bash
# Docker
docker compose logs -f stratum-proxy

# Native
# Watch console output
```

## Troubleshooting

**"Block template not ready"**: Node still syncing, wait for full sync

**Miner can't connect**: Check firewall, verify STRATUM_PORT is correct

**Low hashrate**: Adjust `STATIC_SHARE_DIFFICULTY` for more frequent feedback

**Build fails**: Ensure Docker has enough memory (4GB+ recommended for compilation)

## Advanced

### ZMQ Block Notifications

The proxy uses ZMQ for instant block notifications instead of polling:

- **RXD**: Port 29332 (hashblock), 29333 (rawblock)

Disable with `ENABLE_ZMQ=false` if needed.

### Variable Difficulty

Enable automatic difficulty adjustment per miner:

```bash
ENABLE_VARDIFF=true
VARDIFF_TARGET_SHARE_TIME=15.0    # Target seconds between shares
VARDIFF_MIN_DIFFICULTY=100.0      # Minimum difficulty floor
VARDIFF_MAX_DIFFICULTY=10000000.0 # Maximum difficulty ceiling
VARDIFF_START_DIFFICULTY=10000.0  # Initial difficulty for new miners
```

Additional tuning options (see `.env.example.gpu` or `.env.example.asic` for full list):

```bash
VARDIFF_RETARGET_SHARES=20        # Shares before retargeting
VARDIFF_RETARGET_TIME=300.0       # Max seconds before retargeting
VARDIFF_UP_STEP=2.0               # Multiplier when increasing difficulty
VARDIFF_DOWN_STEP=0.5             # Multiplier when decreasing difficulty
VARDIFF_STATE_PATH=data/vardiff_state.json  # Persist difficulty between restarts
VARDIFF_CHAIN_HEADROOM=0.9        # Fraction of chain difficulty as upper cap
```

### Project Structure

```
rxd_proxy/
├── consensus/    # Block/transaction building
├── db/           # Database schema and queries
├── rpc/          # RPC client implementations
├── state/        # Template state management
├── stratum/      # Stratum protocol server
├── utils/        # Hashing and encoding
├── web/          # Dashboard web interface
└── zmq/          # ZMQ block listeners
```

## License

MIT License - See LICENSE file

## All Environment Variables

### Core Settings

| Variable                   | Description                                            | Default                    |
| -------------------------- | ------------------------------------------------------ | -------------------------- |
| `RXD_RPC_USER`             | Radiant RPC username                                   | radiant_user               |
| `RXD_RPC_PASS`             | Radiant RPC password                                   | -                          |
| `RXD_RPC_PORT`             | Radiant RPC port                                       | 7332                       |
| `RXD_P2P_PORT`             | Radiant P2P port                                       | 7333                       |
| `STRATUM_PORT`             | Stratum proxy port                                     | 54321                      |
| `PROXY_SIGNATURE`          | Custom coinbase signature                              | /radiant-stratum-proxy/    |
| `USE_EASIER_TARGET`        | Enable easier target selection                         | true                       |
| `STATIC_SHARE_DIFFICULTY`  | Static share difficulty (GPU=1, ASIC=512)              | 512.0                      |
| `TESTNET`                  | Use testnet                                            | false                      |
| `LOG_LEVEL`                | Logging level (DEBUG, INFO, WARNING, ERROR)            | INFO                       |
| `SHOW_JOBS`                | Show job updates in logs                               | false                      |
| `ENABLE_ZMQ`               | Enable ZMQ block notifications                         | true                       |
| `RXD_ZMQ_ENDPOINT`         | ZMQ endpoint URL                                       | tcp://radiant:28332        |
| `ENABLE_DASHBOARD`         | Enable web dashboard                                   | false                      |
| `DASHBOARD_PORT`           | Web dashboard port                                     | 8080                       |
| `ENABLE_DATABASE`          | Enable statistics database                             | false                      |
| `DISCORD_WEBHOOK_URL`      | Discord webhook for notifications                      | (blank = disabled)         |
| `TELEGRAM_BOT_TOKEN`       | Telegram bot token                                     | (blank = disabled)         |
| `TELEGRAM_CHAT_ID`         | Telegram chat ID                                       | (blank = disabled)         |

### Variable Difficulty Settings

| Variable                        | Description                                    | Default              |
| ------------------------------- | ---------------------------------------------- | -------------------- |
| `ENABLE_VARDIFF`                | Enable variable difficulty per miner           | false                |
| `VARDIFF_TARGET_SHARE_TIME`     | Target seconds between shares                  | 15.0                 |
| `VARDIFF_MIN_DIFFICULTY`        | Minimum difficulty floor                       | 100.0                |
| `VARDIFF_MAX_DIFFICULTY`        | Maximum difficulty ceiling                     | 10000000.0           |
| `VARDIFF_START_DIFFICULTY`      | Initial difficulty for new miners              | 10000.0              |
| `VARDIFF_RETARGET_SHARES`       | Shares before retargeting                      | 20                   |
| `VARDIFF_RETARGET_TIME`         | Max seconds before retargeting                 | 300.0                |
| `VARDIFF_UP_STEP`               | Multiplier when increasing difficulty          | 2.0                  |
| `VARDIFF_DOWN_STEP`             | Multiplier when decreasing difficulty          | 0.5                  |
| `VARDIFF_EMA_ALPHA`             | EMA smoothing factor                           | 0.3                  |
| `VARDIFF_INACTIVITY_LOWER`      | Seconds before inactivity drop                 | 90.0                 |
| `VARDIFF_INACTIVITY_MULTIPLES`  | Multiples of target time for inactivity        | 6.0                  |
| `VARDIFF_INACTIVITY_DROP_FACTOR`| Factor to reduce difficulty on inactivity      | 0.5                  |
| `VARDIFF_STATE_PATH`            | Path to persist difficulty state               | data/vardiff_state.json |
| `VARDIFF_WARM_START_MINUTES`    | Minutes to use saved difficulty on restart     | 60                   |
| `VARDIFF_CHAIN_HEADROOM`        | Fraction of chain difficulty as upper cap      | 0.9                  |

## Building from Source

Docker automatically builds Radiant from source using https://github.com/Radiant-Core/Radiant-Core (a maintained fork).

### Build Configuration

You can specify a different branch or tag by modifying the build arg in `docker-compose.yml`:

```yaml
radiant:
  build:
    context: .
    dockerfile: Dockerfile.radiant
    args:
      RADIANT_VERSION: master  # or a specific tag like v1.0.0
```

### Manual Build (for native installs)

If running without Docker, build Radiant manually:

```bash
# Install dependencies
sudo apt-get install build-essential cmake ninja-build libboost-all-dev \
    libevent-dev libssl-dev libdb++-dev libminiupnpc-dev libzmq3-dev

# Clone and build
git clone https://github.com/Radiant-Core/Radiant-Core.git
cd Radiant-Core
mkdir build && cd build
cmake -GNinja .. -DBUILD_RADIANT_QT=OFF
ninja

# Binaries are in build/src/
# - radiantd
# - radiant-cli
# - radiant-tx
```

### Services

- **radiant**: Radiant daemon
  - RPC: `localhost:7332`
  - P2P: `localhost:7333`
- **stratum-proxy**: Mining proxy
  - Stratum: `localhost:54321`
  - Dashboard: `localhost:8080`

## Customization

### Proxy Signature

The proxy includes a customizable signature in coinbase transactions to identify your mining setup.

**Configuration Options:**

1. **Environment Variable** (recommended for Docker):

   ```bash
   # In .env file
   PROXY_SIGNATURE=/your-pool-name/
   ```

2. **Command Line Argument**:
   ```bash
   python -m rxd_proxy.run --proxy-signature="/my-custom-signature/" [other args...]
   ```

**Guidelines:**

- Keep it short (max 32 bytes recommended)
- Use forward slashes or other characters to make it recognizable
- Examples: `/MyPool/`, `/Solo-Miner-2025/`, `/RXD-Solo/`

**Default:** `/radiant-stratum-proxy/`

## Usage

### Native Python Execution (Without Docker)

If you prefer to run the proxy directly with Python instead of using Docker:

#### Prerequisites

1. **Python 3.10+** installed on your system
2. **Radiant node** running separately (either locally or remotely)
3. **Python dependencies** installed

#### Setup Steps

1. **Install Python dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

2. **Configure your blockchain node** (optional):

   Copy `config/radiant.conf` to your Radiant data directory:

   **Data directory locations:**

   - Windows: `%APPDATA%\Radiant\`
   - Linux: `~/.radiant/`
   - macOS: `~/Library/Application Support/Radiant/`

3. **Ensure your node is running**:

   - Radiant node accessible via RPC (default: `localhost:7332`)

4. **Run the proxy**:

   **For localhost testing only:**

   ```bash
   python -m rxd_proxy.run \
     --ip=127.0.0.1 \
     --port=54321 \
     --rpcuser=your_rxd_rpc_user \
     --rpcpass=your_rxd_rpc_password \
     --rpcip=127.0.0.1 \
     --rpcport=7332 \
     --use-easier-target \
     --log-level=INFO
   ```

   **For remote miners:**

   ```bash
   python -m rxd_proxy.run \
     --ip=0.0.0.0 \
     --port=54321 \
     --rpcuser=your_rxd_rpc_user \
     --rpcpass=your_rxd_rpc_password \
     --use-easier-target \
     --log-level=INFO
   ```

#### Network Binding Options

| IP Address      | Use Case                | Security | Description                                       |
| --------------- | ----------------------- | -------- | ------------------------------------------------- |
| `127.0.0.1`     | **Testing/Development** | High     | Localhost only - miners must run on same machine  |
| `0.0.0.0`       | **Production Mining**   | Medium   | All interfaces - remote miners can connect        |
| `192.168.1.100` | **Specific Network**    | Medium   | Bind to specific IP - only that network interface |

#### Available Options

Run `python -m rxd_proxy.run --help` to see all available options:

- `--ip`: IP address to bind proxy server on (default: 127.0.0.1)
- `--port`: Stratum port (default: 54321)
- `--rpcip/--rpcport`: Radiant RPC connection
- `--proxy-signature`: Custom coinbase signature
- `--use-easier-target`: Enable easier target selection
- `--testnet`: Use testnet mode
- `--log-level`: Set logging level (DEBUG, INFO, WARNING, ERROR)
- `--jobs`: Show job updates

### Docker Compose Usage

For a complete containerized setup:

#### Start All Services

```bash
docker compose up -d
```

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f stratum-proxy
docker compose logs -f radiant
```

### Stop Services

```bash
docker compose down
```

### Update Configuration

**Linux/macOS:**
```bash
nano .env
docker compose down && docker compose up -d
```

**Windows (PowerShell):**
```powershell
notepad .env
docker compose down; docker compose up -d
```

### Mining

Connect your miner to the stratum proxy:

- **Host**: Your server IP
- **Port**: 54321 (or your configured STRATUM_PORT)
- **Username**: Your Radiant address (e.g., `1YourRadiantAddress.worker1`)
- **Password**: Any value

The first address that connects becomes the payout address for Radiant rewards.

#### Sample Miner Commands

**For SHA512/256d mining:**

```bash
# For localhost testing
miner.exe --algorithm sha512256d --pool localhost:54321 --wallet 1YourRadiantAddress

# For remote server
miner.exe --algorithm sha512256d --pool 192.168.1.100:54321 --wallet 1YourRadiantAddress.worker1
```

**Note**: Replace `1YourRadiantAddress` with your actual Radiant address.

### RPC Command Line Access

You can interact with the blockchain node using RPC commands:

#### Docker Container RPC Commands

**Radiant Commands:**

> **Note:** The `-u radiant` flag is required to run as the radiant user, which has access to the RPC credentials in the configuration file.

```bash
# Get mining information
docker compose exec -u radiant radiant radiant-cli getmininginfo

# Get blockchain info
docker compose exec -u radiant radiant radiant-cli getblockchaininfo

# Get wallet info
docker compose exec -u radiant radiant radiant-cli getwalletinfo

# Generate new address
docker compose exec -u radiant radiant radiant-cli getnewaddress

# Get network connections
docker compose exec -u radiant radiant radiant-cli getconnectioncount
```

#### Native Installation RPC Commands

```bash
# Using configuration file (recommended)
radiant-cli getmininginfo

# Using explicit RPC parameters
radiant-cli -rpcuser=radiant_user -rpcpassword=radiant_password -rpcport=7332 getmininginfo
```

#### Useful RPC Commands for Mining

**Monitor Mining Status:**

```bash
# Check if mining is active
getmininginfo

# Get current block height
getblockcount

# Get network hash rate
getnetworkhashps

# Check wallet balance
getbalance

# List recent transactions
listtransactions
```

### Wallet Setup

**Important**: Before generating addresses, you must first create and load a wallet.

1. **Create Radiant Wallet**:

   ```bash
   # Create a new wallet named "default"
   docker compose exec -u radiant radiant radiant-cli createwallet "default"

   # Load the wallet
   docker compose exec -u radiant radiant radiant-cli loadwallet "default"
   ```

2. **Generate Radiant Address**:

   ```bash
   docker compose exec -u radiant radiant radiant-cli getnewaddress
   ```

### Monitoring

Check blockchain sync status:

```bash
docker compose exec -u radiant radiant radiant-cli getblockchaininfo
```

Check mining info:

```bash
docker compose exec -u radiant radiant radiant-cli getmininginfo
```

## Troubleshooting

### Services Won't Start

- Check Docker logs: `docker compose logs [service-name]`
- Verify `.env` file configuration
- Ensure ports aren't already in use

### Proxy Connection Issues

- Verify daemon is synced
- Check RPC connectivity
- Review proxy logs for errors

### Mining Issues

- Ensure miner is pointing to correct host:port
- Verify wallet address format (Radiant uses legacy P2PKH addresses starting with "1")
- Check proxy logs for submission details

## Security Notes

- Change default RPC passwords in `.env`
- Consider using firewall rules for RPC ports
- Keep wallet backups secure
- Monitor for unauthorized access

## File Structure

```
radiant-stratum-proxy/
├── docker-compose.yml       # Main compose file
├── .env.example.gpu         # GPU mining configuration template
├── .env.example.asic        # ASIC mining configuration template
├── .gitignore               # Git ignore rules
├── Dockerfile               # Proxy container build
├── Dockerfile.radiant       # Radiant node container (builds from source)
├── entrypoint.sh            # Proxy entrypoint script
├── entrypoint-radiant.sh    # Radiant node entrypoint script
├── requirements.txt         # Python dependencies
├── setup.sh / setup.bat     # Setup scripts for different platforms
├── health-check-radiant.sh  # Radiant node health check
├── config/                  # Configuration templates directory
│   └── radiant.conf         # Radiant daemon config template
├── rxd_proxy/               # Proxy application package
│   ├── consensus/           # Block/transaction building
│   ├── db/                  # Database schema and queries
│   ├── rpc/                 # RPC client implementations
│   ├── state/               # Template state management
│   ├── stratum/             # Stratum protocol server
│   ├── utils/               # Hashing and encoding
│   ├── web/                 # Dashboard web interface
│   └── zmq/                 # ZMQ block listeners
└── submit_history/          # Block submission logs
```
