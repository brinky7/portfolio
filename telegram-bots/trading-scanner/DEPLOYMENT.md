# Trading Scanner Agent — Deployment Guide

## Overview

The Trading Scanner Agent is a standalone async Python service that scans 150+ cryptocurrency pairs every 15 minutes, generates Kelly-Criterion-sized trading signals, and publishes them to Redis for the Supervisor/Executor agents.

**Location:** `/srv/brinky-company/agents/departments/trading/scanner/`  
**Systemd service:** `brinky-scanner.service`  
**User:** `clawuser`  
**Python:** 3.10+

---

## Prerequisites

- Redis running on localhost:6379
- CCXT exchange instance (for fallback OHLCV fetching)
- Python 3.10+ with dependencies installed

## Installation

### 1. Install Dependencies

```bash
cd /srv/brinky-company/agents/departments/trading/scanner
pip install -r requirements.txt
```

### 2. Copy Systemd Service

```bash
sudo cp systemd/brinky-scanner.service /etc/systemd/user/
sudo systemctl --user daemon-reload
```

### 3. Configure Environment

Create `.env.local` (optional, overrides defaults):

```bash
cat > /srv/brinky-company/agents/departments/trading/scanner/.env.local <<'EOF'
LOG_LEVEL=DEBUG
REDIS_HOST=localhost
REDIS_PORT=6379
PROMETHEUS_PORT=9100
EXCHANGE_SANDBOX=False
EOF
```

### 4. Ensure Directories

```bash
mkdir -p /srv/brinky-company/agents/departments/trading/scanner/{logs,storage}
chown clawuser:clawuser /srv/brinky-company/agents/departments/trading/scanner
chmod 755 /srv/brinky-company/agents/departments/trading/scanner
```

---

## Running the Scanner

### Start Systemd Service

```bash
# As clawuser (with linger enabled)
systemctl --user start brinky-scanner

# Check status
systemctl --user status brinky-scanner

# View logs
journalctl --user -u brinky-scanner -f
```

### Manual Start (Development)

```bash
cd /srv/brinky-company/agents/departments/trading/scanner
python3 main.py
```

### Enable Auto-Start

```bash
systemctl --user enable brinky-scanner
```

---

## Configuration

All settings in `config.py`:

| Setting | Default | Purpose |
|---------|---------|---------|
| `INTERVAL_SECONDS` | 900 (15m) | Scan cycle frequency |
| `MAX_CONCURRENT_POSITIONS` | 10 | Max open positions |
| `MIN_CONFIDENCE` | 0.65 | Signal confidence threshold |
| `POSITION_SIZE_PCT_NORMAL` | (5%, 10%) | Normal position sizing |
| `KELLY_CRITERION_ENABLED` | True | Kelly Criterion sizing |
| `ATR_STOP_LOSS_MULTIPLIER` | 2.0 | SL distance = ATR × 2.0 |
| `MIN_SL_PCT` | 1.5 | Minimum SL distance % |
| `REDIS_HOST` | localhost | Redis server |
| `REDIS_PORT` | 6379 | Redis port |

---

## Redis Integration

Scanner publishes to:

- **Queue:** `scan_signals` — Signal JSON objects (1-hour TTL)
- **Pub/Sub:** `new_signals` — Notification channel (symbol name)

Consumes from:

- `account:balance` — Current USDT balance
- `open_positions` — Active positions (list)
- `whitelist_pairs` — Allowed symbols (set)
- `volatility:{symbol}` — ATR per pair
- `news_bias:{symbol}` — News sentiment (-1 to +1)
- `correlations` — Pearson correlation matrix

---

## Monitoring

### Prometheus Metrics (Port 9100)

```bash
curl http://localhost:9100/metrics | grep brinky_scanner
```

Key metrics:
- `scanner_scan_latency_seconds` — Cycle duration (histogram)
- `scanner_signals_total{symbol,direction,status}` — Signal counts
- `scanner_redis_queue_depth` — Pending signals
- `scanner_error_rate` — Failure rate

### Logs

- **File:** `/srv/brinky-company/agents/departments/trading/scanner/logs/scanner.log`
- **SQLite:** `/srv/brinky-company/agents/departments/trading/scanner/storage/scanner.db`
- **Systemd:** `journalctl --user -u brinky-scanner -f`

---

## Troubleshooting

### Service Won't Start

```bash
# Check logs
journalctl --user -u brinky-scanner -n 50 -e

# Test manually
cd /srv/brinky-company/agents/departments/trading/scanner
python3 main.py  # Any errors will print immediately
```

### Low Confidence Signals

Check config: `MIN_CONFIDENCE` threshold. Signals below 0.65 are filtered.

### No Signals Generated

1. Verify Redis running: `redis-cli ping` → PONG
2. Check whitelist: `redis-cli SMEMBERS whitelist_pairs`
3. Check balance: `redis-cli GET account:balance`
4. Review logs: `journalctl --user -u brinky-scanner -f`

### High Memory Usage

Check Scanner service with: `systemctl --user show brinky-scanner --property=MemoryCurrent`

---

## Performance

- **Scan latency (p95):** ~2-3 seconds per cycle (150 pairs)
- **Memory footprint:** ~80-150 MB at rest
- **CPU:** <10% per cycle

---

## Updates

To update scanner code:

```bash
cd /srv/brinky-company
git pull origin master

# Restart service
systemctl --user restart brinky-scanner
```

---

## Security

Systemd service runs with:
- User isolation (`clawuser`)
- Read-only filesystem (except logs/, storage/)
- No new privileges
- Private /tmp

Never:
- Run as root
- Hardcode credentials in env
- Use testnet OHLCV for signals
