# Notifications Setup Guide

The Radiant Stratum Proxy supports Discord and Telegram notifications for important mining events.

## Notification Events

The proxy can send notifications for:

- **Block Found** - When a share meets network difficulty and a block is submitted
- **Miner Connected** - When a new mining worker connects to the proxy
- **Miner Disconnected** - When a mining worker disconnects from the proxy

## Discord Setup

### Creating a Discord Webhook

1. Open your Discord server settings
2. Go to **Integrations** → **Webhooks**
3. Click **New Webhook**
4. Configure the webhook:
   - Set a name (e.g., "Mining Bot")
   - Choose the channel for notifications
5. Click **Copy Webhook URL**
6. Add to your `.env` file:

```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_URL
```

### Discord Notification Format

Block notifications include:

- 🎉 Block found announcement
- Block height
- Transaction hash
- Mining pool/address info

## Telegram Setup

### Creating a Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the **bot token** provided
4. Add to your `.env` file:

```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

### Getting Your Chat ID

1. Start a chat with your new bot
2. Send any message to the bot
3. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Find `"chat":{"id":XXXXXXXXX}` in the response
5. Add to your `.env` file:

```bash
TELEGRAM_CHAT_ID=your_chat_id_here
```

### Group Chat Setup

To receive notifications in a group:

1. Add your bot to the group
2. Send a message mentioning the bot
3. Use the getUpdates method above to find the group chat ID (usually negative)

## Environment Variables

| Variable               | Description             | Required |
| ---------------------- | ----------------------- | -------- |
| `DISCORD_WEBHOOK_URL`  | Discord webhook URL     | Optional |
| `TELEGRAM_BOT_TOKEN`   | Telegram bot API token  | Optional |
| `TELEGRAM_CHAT_ID`     | Telegram chat/group ID  | Optional |
| `ENABLE_NOTIFICATIONS` | Enable/disable all      | Optional |

## Testing Notifications

### Test Discord

```bash
curl -H "Content-Type: application/json" \
     -d '{"content":"Test notification from Radiant Proxy"}' \
     YOUR_DISCORD_WEBHOOK_URL
```

### Test Telegram

```bash
curl "https://api.telegram.org/botYOUR_BOT_TOKEN/sendMessage?chat_id=YOUR_CHAT_ID&text=Test"
```

## Notification Examples

### Block Found (Discord)

```
🎉 **RXD Block Found!**
Height: 123456
Hash: 00000000000000000003...
Reward: 25,000 RXD
```

### Miner Connected (Telegram)

```
⛏️ New miner connected
Worker: 1YourAddress.worker1
IP: 192.168.1.100
```

## Troubleshooting

### Discord notifications not working

- Verify webhook URL is correct and complete
- Check Discord server permissions
- Ensure webhook channel exists

### Telegram notifications not working

- Verify bot token is correct
- Ensure you've started a chat with the bot first
- Check that chat ID is correct (use getUpdates to verify)
- For groups, ensure bot has permission to send messages

### No notifications at all

- Check `ENABLE_NOTIFICATIONS` is not set to `false`
- Review proxy logs for notification errors
- Verify network connectivity to Discord/Telegram APIs
