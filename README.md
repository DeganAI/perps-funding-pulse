# Perps Funding Pulse - Real-Time Perpetual Funding Rates

**Bounty #8 Submission for Daydreams AI Agent Bounties**

Real-time perpetual futures funding rate oracle providing current funding rates, time until next payment, open interest, and long/short skew across major centralized and decentralized perpetuals exchanges.

## Features

- **Real-Time Funding Rates**: Current funding rates (% per 8h) from major exchanges
- **Payment Timing**: Seconds until next funding payment
- **Open Interest**: Total open interest in USD
- **Market Skew**: Long/short skew ratio (-1 to 1)
- **Multi-Venue Support**: CEX (Binance, Bybit, OKX) and DEX (Hyperliquid)
- **x402 Payments**: Usage-based micropayments via daydreams facilitator

## Supported Venues

### Centralized Exchanges (CEX)
- **Binance Futures** - USDT-margined perpetuals
- **Bybit** - Unified trading account perpetuals
- **OKX** - Perpetual swaps

### Decentralized Exchanges (DEX)
- **Hyperliquid** - L1 perpetuals exchange

### Coming Soon
- dYdX (Ethereum/StarkNet)
- GMX (Arbitrum/Avalanche)

## API Endpoints

### POST /perps/funding
Get current funding rates and open interest for specified markets

**Request:**
```json
{
  "venue_ids": ["binance", "bybit", "okx"],
  "markets": ["BTC/USDT:USDT", "ETH/USDT:USDT"]
}
```

**Response:**
```json
{
  "total_markets": 6,
  "markets": [
    {
      "venue": "binance",
      "market": "BTC/USDT:USDT",
      "funding_rate": 0.01,
      "time_to_next": 14400,
      "open_interest": 5000000000.00,
      "skew": 0.25,
      "mark_price": 45000.00,
      "index_price": 44995.00,
      "timestamp": "2025-10-31T12:00:00Z"
    }
  ],
  "timestamp": "2025-10-31T12:00:00Z"
}
```

### POST /entrypoints/perps-funding-pulse/invoke
AP2-compatible entrypoint (requires x402 payment in production)

### GET /venues
List all supported perpetuals exchanges

### GET /health
Service health check

## Quick Start

### Local Development

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Set environment variables:**
```bash
export PORT=8000
export FREE_MODE=true
export PAYMENT_ADDRESS=0x01D11F7e1a46AbFC6092d7be484895D2d505095c
export BASE_URL=http://localhost:8000
```

3. **Run the server:**
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

4. **Test the API:**
```bash
curl -X POST http://localhost:8000/perps/funding \
  -H "Content-Type: application/json" \
  -d '{
    "venue_ids": ["binance", "bybit"],
    "markets": ["BTC/USDT:USDT", "ETH/USDT:USDT"]
  }'
```

### Docker

```bash
docker build -t perps-funding-pulse .
docker run -p 8000:8000 \
  -e FREE_MODE=true \
  -e PAYMENT_ADDRESS=0x01D11F7e1a46AbFC6092d7be484895D2d505095c \
  perps-funding-pulse
```

## Deployment

### Railway

1. **Create new Railway project**
2. **Connect GitHub repository**
3. **Set environment variables:**
   - `PORT=8000`
   - `FREE_MODE=false` (for production)
   - `PAYMENT_ADDRESS=0x01D11F7e1a46AbFC6092d7be484895D2d505095c`
   - `BASE_URL=https://your-service-production.up.railway.app`

4. **Deploy** - Railway will automatically build using Dockerfile

## x402 Protocol

### AP2 Metadata
- Endpoint: `GET /.well-known/agent.json` (returns HTTP 200)
- Contains service description, schemas, and payment info

### x402 Payment Info
- Endpoint: `GET /.well-known/x402` (returns HTTP 402)
- Network: Base
- Price: 0.05 USDC per request
- Payee: `0x01D11F7e1a46AbFC6092d7be484895D2d505095c`
- Asset: `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` (USDC on Base)
- Facilitator: `https://facilitator.daydreams.systems`

## Technical Details

### Funding Rate Calculation
- Funding rate = (mark_price - index_price) / index_price
- Expressed as % per 8 hours (standard interval)
- Positive rate: Longs pay shorts (more longs)
- Negative rate: Shorts pay longs (more shorts)

### Funding Payment Schedule
- **Most exchanges**: Every 8 hours (00:00, 08:00, 16:00 UTC)
- **Hyperliquid**: Every 1 hour
- **dYdX**: Every 1 hour

### Skew Calculation
- `skew = (long_OI - short_OI) / total_OI`
- Range: -1.0 (all shorts) to +1.0 (all longs)
- Approximated from funding rate when direct data unavailable

### Market Symbol Format
Markets use CCXT unified symbol format:
- `BTC/USDT:USDT` - BTC perpetual margined in USDT
- `ETH/USDT:USDT` - ETH perpetual margined in USDT

## Data Sources

### Binance Futures
- API: `GET /fapi/v1/premiumIndex` (funding rates)
- API: `GET /fapi/v1/openInterest` (open interest)

### Bybit
- API: `GET /v5/market/tickers` (category=linear)

### OKX
- API: `GET /api/v5/public/funding-rate`
- API: `GET /api/v5/public/open-interest`
- API: `GET /api/v5/market/ticker`

### Hyperliquid
- API: `POST /info` (type=meta, metaAndAssetCtxs)

## Acceptance Criteria

✅ **Real-time Data**: Funding rates updated every request from live APIs
✅ **Multi-Venue**: Supports 4+ major exchanges (Binance, Bybit, OKX, Hyperliquid)
✅ **Complete Data**: Returns funding_rate, time_to_next, open_interest, skew
✅ **Accurate**: Matches venue UI data within acceptable tolerance
✅ **x402 Compliant**: Full AP2 + x402 protocol implementation
✅ **Production Ready**: Deployed on Railway with health checks

## Architecture

```
perps-funding-pulse/
├── src/
│   ├── main.py              # FastAPI app with AP2/x402 endpoints
│   ├── perps_fetcher.py     # Funding data fetcher for all venues
│   └── x402_middleware.py   # Payment verification middleware
├── static/                  # Static assets
├── requirements.txt         # Python dependencies
├── railway.toml            # Railway deployment config
├── Dockerfile              # Container definition
└── README.md               # This file
```

## Development

### Testing Endpoints

```bash
# Health check
curl http://localhost:8000/health

# List venues
curl http://localhost:8000/venues

# Get funding data
curl -X POST http://localhost:8000/perps/funding \
  -H "Content-Type: application/json" \
  -d '{
    "venue_ids": ["binance"],
    "markets": ["BTC/USDT:USDT"]
  }'

# Check AP2 metadata
curl http://localhost:8000/.well-known/agent.json

# Check x402 metadata
curl http://localhost:8000/.well-known/x402
```

## License

MIT License - Built for Daydreams AI Agent Bounties

## Author

**Ian B** (hashmonkey@degenai.us)
DeganAI - Bounty #8 Submission

## Links

- **Live Service**: https://perps-funding-pulse-production.up.railway.app
- **API Docs**: https://perps-funding-pulse-production.up.railway.app/docs
- **x402scan**: https://www.x402scan.com
- **Bounty Program**: https://github.com/daydreamsai/agent-bounties
