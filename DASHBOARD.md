# Mining Dashboard Guide

The Radiant Stratum Proxy includes an optional web-based dashboard for real-time monitoring of your mining operation.

## Quick Start

Enable the dashboard in your `.env` file:

```bash
ENABLE_DASHBOARD=true
DASHBOARD_PORT=8080
ENABLE_DATABASE=true  # Required for historical data
```

Then access the dashboard at: `http://localhost:8080`

For a quick setup guide, see [DASHBOARD_QUICKSTART.md](DASHBOARD_QUICKSTART.md).

## Features

### Real-Time Mining Statistics

- **Current hashrate** - Calculated from recent share submissions
- **Active workers** - Number of connected mining workers
- **Network difficulty** - Current Radiant network difficulty
- **Block height** - Current blockchain height
- **Time to find** - Estimated time to find a block based on hashrate

### Block History

- Recent blocks found by the pool
- Block height and timestamp
- Confirmation status
- Block reward amount

### Live Share Feed

- Real-time share submissions
- Worker identification
- Difficulty and validity status
- WebSocket-powered updates

### Miner Details

- Individual worker hashrates
- Connection duration
- Share statistics per worker

## Dashboard Pages

### Main Dashboard (`/`)

The primary monitoring interface showing:

- Mining statistics overview
- Current hashrate and worker count
- Recent blocks found
- Time to find estimate

### Shares View (`/shares.html`)

Live feed of share submissions:

- Real-time share stream via WebSocket
- Worker identification
- Share difficulty
- Submission timestamps

## Configuration

### Environment Variables

| Variable           | Description                       | Default |
| ------------------ | --------------------------------- | ------- |
| `ENABLE_DASHBOARD` | Enable/disable web dashboard      | false   |
| `DASHBOARD_PORT`   | Port for web dashboard            | 8080    |
| `ENABLE_DATABASE`  | Enable SQLite for historical data | false   |

### Database

The dashboard works best with the database enabled:

```bash
ENABLE_DATABASE=true
```

This stores:

- Block history
- Share statistics
- Worker information
- Historical hashrate data

Database location: `./data/mining.db`

## API Endpoints

The dashboard uses these REST API endpoints:

### GET `/api/stats`

Returns current mining statistics:

```json
{
  "hashrate": 1500000000,
  "workers": 3,
  "difficulty": 12345678.9,
  "height": 123456,
  "ttf_seconds": 3600
}
```

### GET `/api/blocks`

Returns recent blocks found:

```json
{
  "blocks": [
    {
      "height": 123456,
      "hash": "00000000...",
      "time": "2025-01-15T12:00:00Z",
      "confirmations": 10
    }
  ]
}
```

### GET `/api/workers`

Returns connected worker information:

```json
{
  "workers": [
    {
      "name": "1YourAddress.worker1",
      "hashrate": 500000000,
      "shares": 150,
      "connected": "2025-01-15T10:00:00Z"
    }
  ]
}
```

### WebSocket `/ws/shares`

Real-time share feed via WebSocket connection.

## Security Considerations

### Network Exposure

By default, the dashboard binds to all interfaces when running in Docker. For production:

1. **Use a reverse proxy** (nginx, Caddy) with authentication
2. **Firewall rules** to restrict access
3. **VPN** for remote access

### No Built-in Authentication

The dashboard does not include authentication. Options:

- Use reverse proxy with basic auth
- Restrict access via firewall
- Bind to localhost only (`127.0.0.1`)

## Customization

### Dashboard Files

Static files are located in:

```
rxd_proxy/web/static/
├── index.html      # Main dashboard
├── dashboard.css   # Dashboard styles
├── shares.html     # Shares view
└── shares.css      # Shares styles
```

### Modifying the Dashboard

You can customize the dashboard by editing the HTML/CSS files. Changes take effect on next proxy restart.

## Troubleshooting

### Dashboard not accessible

- Verify `ENABLE_DASHBOARD=true` in `.env`
- Check port is not in use: `netstat -an | grep 8080`
- Ensure firewall allows connections on dashboard port

### No data showing

- Verify `ENABLE_DATABASE=true` if historical data needed
- Check proxy logs for database errors
- Ensure miners are connected and submitting shares

### WebSocket connection failed

- Verify proxy is running
- Check browser console for errors
- Ensure WebSocket port is accessible

### Stale data

- Dashboard auto-refreshes every few seconds
- Force refresh with Ctrl+F5
- Check proxy is still running

## Docker Compose Setup

The dashboard port is exposed in `docker-compose.yml`:

```yaml
stratum-proxy:
  ports:
    - "${STRATUM_PORT:-54321}:${STRATUM_PORT:-54321}"
    - "${DASHBOARD_PORT:-8080}:${DASHBOARD_PORT:-8080}"
```

Access via: `http://your-server-ip:8080`

## Performance

The dashboard is lightweight and designed for efficiency:

- Minimal JavaScript dependencies
- WebSocket for real-time updates (no polling)
- SQLite for fast local queries
- Static file serving built into Python

For high-traffic pools, consider:

- Reverse proxy with caching
- CDN for static assets
- Separate database server
