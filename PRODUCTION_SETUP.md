# Production Setup Guide - Perps Funding Pulse

Complete guide for deploying Perps Funding Pulse to production on Railway.

## Pre-Deployment Checklist

- [ ] Code complete and tested locally
- [ ] All dependencies in requirements.txt
- [ ] Dockerfile builds successfully
- [ ] railway.toml configured
- [ ] .gitignore includes sensitive files
- [ ] README.md complete

## Railway Deployment

### Step 1: Create Railway Project

1. Go to https://railway.app
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Connect your GitHub account
5. Select the `perps-funding-pulse` repository

### Step 2: Configure Environment Variables

In Railway dashboard, add these variables:

```bash
PORT=8000
FREE_MODE=false
PAYMENT_ADDRESS=0x01D11F7e1a46AbFC6092d7be484895D2d505095c
BASE_URL=https://perps-funding-pulse-production.up.railway.app
```

**Important Notes:**
- `PORT` must be 8000
- `FREE_MODE=false` enables payment verification in production
- `PAYMENT_ADDRESS` is the Base wallet for receiving USDC payments
- `BASE_URL` should match your Railway domain (update after first deploy)

### Step 3: Deploy

1. Railway will automatically detect the Dockerfile
2. Builder will be set to "DOCKERFILE" (from railway.toml)
3. Click "Deploy"
4. Wait for build to complete (~2-3 minutes)

### Step 4: Verify Deployment

```bash
# Check health
curl https://perps-funding-pulse-production.up.railway.app/health

# Verify AP2 metadata (should return 200)
curl -I https://perps-funding-pulse-production.up.railway.app/.well-known/agent.json

# Verify x402 metadata (should return 402)
curl -I https://perps-funding-pulse-production.up.railway.app/.well-known/x402

# Test funding endpoint
curl -X POST https://perps-funding-pulse-production.up.railway.app/perps/funding \
  -H "Content-Type: application/json" \
  -d '{
    "venue_ids": ["binance"],
    "markets": ["BTC/USDT:USDT"]
  }'
```

### Step 5: Update BASE_URL

1. Copy your Railway domain (e.g., `perps-funding-pulse-production.up.railway.app`)
2. Update `BASE_URL` environment variable in Railway dashboard
3. Redeploy the service

## x402scan Registration

### Step 1: Verify Entrypoint

```bash
# Should return HTTP 402 with x402 schema
curl -s https://perps-funding-pulse-production.up.railway.app/entrypoints/perps-funding-pulse/invoke
```

### Step 2: Register on x402scan

1. Go to https://www.x402scan.com/resources/register
2. Enter entrypoint URL:
   ```
   https://perps-funding-pulse-production.up.railway.app/entrypoints/perps-funding-pulse/invoke
   ```
3. Leave headers blank
4. Click "Add"
5. Verify "Resource Added" confirmation

### Step 3: Verify Registration

1. Go to https://www.x402scan.com
2. Search for "Perps Funding Pulse"
3. Confirm service is listed

## Monitoring

### Railway Dashboard

Monitor these metrics:
- **CPU Usage**: Should be < 50% average
- **Memory**: Should be < 512MB
- **Response Time**: Should be < 2s for funding requests
- **Error Rate**: Should be < 1%

### Health Checks

Railway performs automatic health checks via `/health` endpoint every 30 seconds.

### Logs

View logs in Railway dashboard:
```bash
# Or use Railway CLI
railway logs
```

## Troubleshooting

### Service Won't Start

1. Check Railway logs for errors
2. Verify all environment variables are set
3. Ensure Dockerfile builds locally:
   ```bash
   docker build -t perps-funding-pulse .
   docker run -p 8000:8000 perps-funding-pulse
   ```

### 502 Bad Gateway

- Service may be restarting (wait 30s)
- Check health endpoint is responding
- Verify PORT environment variable is 8000

### x402scan Registration Fails

1. Verify entrypoint returns HTTP 402:
   ```bash
   curl -I https://your-url/entrypoints/perps-funding-pulse/invoke
   ```
2. Ensure x402 response includes ALL required fields
3. Check agent.json returns HTTP 200

### API Returning Errors

1. Check venue APIs are accessible
2. Verify market symbols are correct format
3. Review application logs in Railway

## Security

### Environment Variables

**Never commit these to git:**
- Private keys
- API keys
- Wallet addresses (use environment variables)

### Payment Address

The payment address `0x01D11F7e1a46AbFC6092d7be484895D2d505095c` is:
- Base network wallet
- Receives USDC payments (contract: `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`)
- Controlled by DeganAI

### Rate Limiting

Consider adding rate limiting in production:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
```

## Scaling

### Horizontal Scaling

Railway supports horizontal scaling:
1. Go to Settings > Scaling
2. Add more replicas
3. Railway handles load balancing

### Caching

Consider adding Redis for caching funding data:
- Cache TTL: 30-60 seconds
- Reduces API calls to exchanges
- Improves response times

## Maintenance

### Updating Code

1. Push changes to GitHub main branch
2. Railway auto-deploys on push
3. Zero-downtime deployment via health checks

### Database (Optional)

For historical data tracking, add Railway PostgreSQL:
1. Add PostgreSQL service in Railway
2. Connect via environment variable
3. Store funding rate history

### Monitoring (Optional)

Add external monitoring:
- **Uptime Robot**: https://uptimerobot.com
- **Better Uptime**: https://betteruptime.com
- Alert on downtime or high response times

## Cost Estimation

### Railway Pricing

- **Starter Plan**: $5/month base
- **Usage**: ~$0.01 per hour of compute
- **Estimated**: $10-15/month for moderate traffic

### API Costs

All venue APIs used are free:
- Binance Futures API: Free
- Bybit API: Free
- OKX API: Free
- Hyperliquid API: Free

## Support

### Issues

Report issues via GitHub Issues

### Contact

**DeganAI Team**
- Email: hashmonkey@degenai.us
- GitHub: https://github.com/DeganAI

## Next Steps

1. ✅ Deploy to Railway
2. ✅ Register on x402scan
3. ✅ Submit bounty PR to daydreamsai/agent-bounties
4. Monitor service performance
5. Add more venues (dYdX, GMX)
6. Implement historical data tracking
7. Add WebSocket support for real-time updates
