# Subscription Telegram Bot

Production Telegram bot with tiered subscription system, crypto payments, quota management, and AI-generated comments.

**Stack:** Python 3.12, python-telegram-bot 20.x, Redis, SQLite, CryptoBot API, Anthropic Claude API

---

## Features

- **4-tier subscription system** — Trial / Basic / Pro / Elite with per-day and per-month limits
- **Crypto payments** via CryptoBot API (USDT, TON, BTC) with 30-day auto-expiry
- **Telegram Stars** payments as alternative payment method
- **Quota enforcement** — per-day request limits per tier, rate limiting
- **Referral system** — unique ref codes, bonus credits on successful referrals
- **AI comments** — Claude API (Haiku) adds analytical commentary to reports
- **Price alerts** — per-asset alerts with tier-based limits
- **Watchlist** — personal asset watchlist with tier-based limits
- **Winrate tracking** — tracks signal accuracy over time
- **Card generator** — visual summary cards for sharing
- **Admin commands** — user management, tier overrides, broadcast

---

## Architecture

```
bot/
  handlers.py        # all command and callback handlers
  tiers.py           # subscription tiers, limits, Redis-backed tier storage
  quota.py           # per-day quota check + consume + rate limiting
  payments.py        # CryptoBot invoice creation and verification
  stars.py           # Telegram Stars payment flow
  referral.py        # ref code generation, tracking, bonus credits
  alerts.py          # price alert storage and management
  watchlist.py       # personal watchlist per user
  ai_comment.py      # Claude API integration for report commentary
  formatter.py       # output formatting for analysis reports
  menus.py           # inline keyboard menus
  db_users.py        # SQLite user registry
  analysis_log.py    # signal logging and history
  winrate.py         # winrate calculation from signal log
  card_generator.py  # visual card generation
  redis_client.py    # shared Redis connection
```

---

## Subscription Tiers

| Tier  | Price   | Requests/day | Alerts | Watchlist |
|-------|---------|--------------|--------|-----------|
| Trial | Free    | 3 (3 days)   | 2      | 3         |
| Basic | $19/mo  | 5            | 5      | 10        |
| Pro   | $49/mo  | 15           | 15     | 30        |
| Elite | $149/mo | Unlimited    | 50     | 100       |

---

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env  # fill in your tokens
redis-server &
python main.py
```

## Requirements

```
python-telegram-bot>=20.0
anthropic>=0.25.0
httpx>=0.27.0
redis>=5.0.0
Pillow>=10.0.0
```
