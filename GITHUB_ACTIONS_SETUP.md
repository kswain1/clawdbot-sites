# Aura-V 2.0 GitHub Actions Pulse Relay

## Overview
This directory contains the **GitHub Actions Cron Job** that powers the Aura-V 2.0 multi-channel alert system. It runs every 15 minutes, fetches XAUUSD data, analyzes it using Aura-V 2.0 logic, and broadcasts alerts to Discord + updates the website.

## Architecture
```
GitHub Actions (Cron: */15 * * * *)
    │
    ├─► Fetch XAUUSD via yfinance
    ├─► Run Aura-V 2.0 Probability Engine
    ├─► Send Discord Alert (via Webhook)
    └─► Commit Pulse Log (for website sync)
```

## Setup Instructions

### 1. Discord Webhooks
You need to create two Discord webhooks:

**For #alerts channel:**
1. Go to your Discord server
2. Right-click #alerts → Integrations → Webhooks
3. Create webhook named "Aura Relay"
4. Copy the webhook URL

**For #inbox channel:**
1. Repeat for #inbox channel
2. Copy that webhook URL too

### 2. GitHub Secrets
Add these secrets to your GitHub repository:

1. Go to: `Settings` → `Secrets and variables` → `Actions`
2. Click `New repository secret`
3. Add:
   - Name: `DISCORD_WEBHOOK_ALERTS`
   - Value: Your #alerts webhook URL
4. Repeat for:
   - Name: `DISCORD_WEBHOOK_INBOX`
   - Value: Your #inbox webhook URL

### 3. Enable GitHub Actions
1. Go to `Actions` tab in your repository
2. Enable workflows if prompted
3. The `aura-pulse.yml` workflow will start running every 15 minutes

## Files

| File | Purpose |
|------|---------|
| `.github/workflows/aura-pulse.yml` | GitHub Actions cron configuration |
| `alert_relay.py` | Main relay script (fetches data, analyzes, sends alerts) |
| `pulse_log.json` | Local log of all pulses (synced to website) |

## Alert Logic

- **Probability > 75%**: STAGE 1 [800s] trigger sent to #alerts
- **Probability 50-75%**: Sent to #inbox only (monitoring)
- **Probability < 50%**: Sent to #inbox only (consolidation)

## Manual Trigger
You can manually trigger a pulse:
1. Go to `Actions` tab
2. Select `Aura-V 2.0 Pulse Relay`
3. Click `Run workflow`

## Monitoring
Check the Actions tab to see:
- Success/failure of each pulse
- Logs showing price fetched and probability calculated
- Discord delivery confirmations
