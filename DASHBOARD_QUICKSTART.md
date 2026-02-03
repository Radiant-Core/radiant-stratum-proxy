# Dashboard Quick Start

Get the mining dashboard running in 2 minutes.

## 1. Enable Dashboard

Add these lines to your `.env` file:

```bash
ENABLE_DASHBOARD=true
DASHBOARD_PORT=8080
ENABLE_DATABASE=true
```

## 2. Restart the Proxy

**Docker:**

```bash
docker compose down
docker compose up -d
```

**Native Python:**

```bash
# Stop the running proxy (Ctrl+C), then:
python -m rxd_proxy.run [your options]
```

## 3. Access Dashboard

Open in your browser: **http://localhost:8080**

## What You'll See

### Main Dashboard

- **Hashrate** - Total pool hashrate from all workers
- **Workers** - Number of connected miners
- **Network Difficulty** - Current RXD network difficulty
- **Block Height** - Current blockchain height
- **Time to Find** - Estimated time to find a block
- **Recent Blocks** - Blocks found by the pool

### Shares Page (`/shares.html`)

- Live stream of share submissions
- Worker names and share difficulties
- Real-time WebSocket updates

## Troubleshooting

**Can't access dashboard?**

- Check `ENABLE_DASHBOARD=true` is set
- Verify port 8080 is not blocked by firewall
- Try `http://127.0.0.1:8080` if on same machine

**No statistics showing?**

- Wait for miners to connect and submit shares
- Ensure `ENABLE_DATABASE=true` for historical data
- Check proxy logs for errors

**Remote access not working?**

- Ensure Docker is binding to `0.0.0.0` not `127.0.0.1`
- Check firewall allows port 8080
- Use your server's IP address, not localhost

## Next Steps

- Read [DASHBOARD.md](DASHBOARD.md) for full documentation
- Configure [notifications](NOTIFICATIONS.md) for block alerts
- Customize dashboard CSS in `rxd_proxy/web/static/`
