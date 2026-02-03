@echo off
REM Radiant Stratum Proxy Setup Script for Windows

echo [*] Setting up Radiant Stratum Proxy...

REM Check if Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not installed. Please install Docker Desktop first.
    pause
    exit /b 1
)

REM Check if Docker Compose is available
docker-compose --version >nul 2>&1
if errorlevel 1 (
    docker compose version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Docker Compose is not available. Please install Docker Compose.
        pause
        exit /b 1
    )
)

REM Create .env file if it doesn't exist
if not exist .env (
    echo [*] Creating .env file...
    
    REM Generate random password (simplified for Windows)
    set RXD_PASS=rxd_%RANDOM%_%RANDOM%
    
    (
        echo # Radiant Node Configuration
        echo RXD_RPC_USER=radiant_user
        echo RXD_RPC_PASS=%RXD_PASS%
        echo RXD_RPC_PORT=7332
        echo RXD_P2P_PORT=7333
        echo RXD_ZMQ_PORT=29332
        echo RXD_ZMQ_RAW_PORT=29333
        echo.
        echo # Stratum Proxy Configuration
        echo STRATUM_PORT=54321
        echo TESTNET=false
        echo LOG_LEVEL=INFO
        echo SHOW_JOBS=false
        echo USE_EASIER_TARGET=true
        echo.
        echo # ZMQ Configuration
        echo ENABLE_ZMQ=true
        echo RXD_ZMQ_ENDPOINT=tcp://radiant:29332
        echo.
        echo # Dashboard Configuration
        echo ENABLE_DASHBOARD=true
        echo DASHBOARD_PORT=8080
        echo.
        echo # Database Configuration ^(for historical data^)
        echo ENABLE_DATABASE=true
        echo.
        echo # Variable Difficulty ^(optional^)
        echo ENABLE_VARDIFF=false
        echo VARDIFF_TARGET_SHARE_TIME=15.0
        echo VARDIFF_MIN_DIFFICULTY=0.00001
        echo VARDIFF_MAX_DIFFICULTY=0.1
        echo.
        echo # Notifications ^(optional - fill in to enable^)
        echo # DISCORD_WEBHOOK_URL=
        echo # TELEGRAM_BOT_TOKEN=
        echo # TELEGRAM_CHAT_ID=
    ) > .env
    
    echo [OK] .env file created with random password
) else (
    echo [OK] .env file already exists
)

REM Create data directories
if not exist submit_history mkdir submit_history
if not exist data mkdir data

echo [OK] Data directories created

REM Check binaries
echo [*] Checking binaries...
if exist check-binaries.bat call check-binaries.bat

REM Build and start services
echo [*] Building and starting services...
docker compose build --no-cache
docker compose up -d

echo.
echo [SUCCESS] Setup complete!
echo.
echo [*] Service Status:
docker compose ps

echo.
echo [*] Next Steps:
echo 1. Wait for blockchain sync (check with: docker compose logs -f radiant)
echo 2. Connect your miner to localhost:54321
echo 3. View dashboard at http://localhost:8080
echo.
echo [*] Commands:
echo   View logs:     docker compose logs -f
echo   Stop services: docker compose down
echo   Restart:       docker compose restart
echo.
echo [*] Monitoring:
echo   RXD status:   docker compose exec radiant radiant-cli getblockchaininfo
echo   Proxy logs:   docker compose logs -f stratum-proxy

pause
