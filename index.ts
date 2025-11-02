import { createAgentApp } from '@lucid-dreams/agent-kit';
import { Hono } from 'hono';

// ============================================
// STEP 1: Environment & Configuration
// ============================================
console.log('[STARTUP] ===== PERPS FUNDING PULSE =====');
console.log('[STARTUP] Step 1: Loading environment variables...');

const PORT = parseInt(process.env.PORT || '3000', 10);
const HOST = '0.0.0.0';
const FACILITATOR_URL = process.env.FACILITATOR_URL || 'https://facilitator.cdp.coinbase.com';
const WALLET_ADDRESS = process.env.ADDRESS || '0x01D11F7e1a46AbFC6092d7be484895D2d505095c';
const NETWORK = process.env.NETWORK || 'base';
const DEFAULT_PRICE = process.env.DEFAULT_PRICE || '$0.05';

console.log('[CONFIG] Port:', PORT);
console.log('[CONFIG] Host:', HOST);
console.log('[CONFIG] Facilitator URL:', FACILITATOR_URL ? 'Set ✓' : 'Not set ✗');
console.log('[CONFIG] Wallet Address:', WALLET_ADDRESS ? 'Set ✓' : 'Not set ✗');
console.log('[CONFIG] Network:', NETWORK);
console.log('[CONFIG] Default Price:', DEFAULT_PRICE);

// ============================================
// STEP 2: Perps Data Fetching
// ============================================
console.log('[STARTUP] Step 2: Configuring exchange APIs...');

interface FundingData {
  venue: string;
  market: string;
  funding_rate: number;
  time_to_next: number;
  open_interest: number;
  skew: number | null;
  mark_price: number | null;
  index_price: number | null;
  timestamp: string;
}

const VENUE_CONFIG = {
  binance: { name: 'Binance Futures', api_url: 'https://fapi.binance.com', enabled: true },
  bybit: { name: 'Bybit', api_url: 'https://api.bybit.com', enabled: true },
  okx: { name: 'OKX', api_url: 'https://www.okx.com', enabled: true },
  hyperliquid: { name: 'Hyperliquid', api_url: 'https://api.hyperliquid.xyz', enabled: true },
};

function getSupportedVenues(): string[] {
  return Object.entries(VENUE_CONFIG)
    .filter(([_, config]) => config.enabled)
    .map(([id, _]) => id);
}

function calculateTimeToNextFunding(): number {
  const now = new Date();
  const currentHour = now.getUTCHours();
  const currentMinute = now.getUTCMinutes();
  const currentSecond = now.getUTCSeconds();

  const nextFundingHours = [0, 8, 16];
  const nextHour = nextFundingHours.find(h => h > currentHour) ?? 24;

  let hoursUntil: number;
  if (nextHour === 24) {
    hoursUntil = (24 - currentHour);
  } else {
    hoursUntil = nextHour - currentHour;
  }

  const timeToNext = hoursUntil * 3600 - (currentMinute * 60 + currentSecond);
  return Math.max(0, Math.floor(timeToNext));
}

async function fetchBinanceFunding(market: string): Promise<FundingData | null> {
  try {
    const symbol = market.replace('/', '').replace(':USDT', '');
    const url = `${VENUE_CONFIG.binance.api_url}/fapi/v1/premiumIndex?symbol=${symbol}`;

    const response = await fetch(url);
    if (!response.ok) return null;
    const data = await response.json();

    const oiUrl = `${VENUE_CONFIG.binance.api_url}/fapi/v1/openInterest?symbol=${symbol}`;
    const oiResponse = await fetch(oiUrl);
    const oiData = oiResponse.ok ? await oiResponse.json() : {};

    const fundingRate = parseFloat(data.lastFundingRate || '0') * 100;
    const markPrice = parseFloat(data.markPrice || '0');
    const openInterest = parseFloat(oiData.openInterest || '0') * markPrice;
    const skew = fundingRate !== 0 ? Math.min(Math.max(fundingRate / 0.1, -1.0), 1.0) : 0.0;

    return {
      venue: 'binance',
      market,
      funding_rate: fundingRate,
      time_to_next: calculateTimeToNextFunding(),
      open_interest: openInterest,
      skew,
      mark_price: markPrice,
      index_price: parseFloat(data.indexPrice || '0'),
      timestamp: new Date().toISOString(),
    };
  } catch (error) {
    console.error(`[BINANCE] Error fetching ${market}:`, error);
    return null;
  }
}

async function fetchBybitFunding(market: string): Promise<FundingData | null> {
  try {
    const symbol = market.replace('/', '').replace(':USDT', '');
    const url = `${VENUE_CONFIG.bybit.api_url}/v5/market/tickers?category=linear&symbol=${symbol}`;

    const response = await fetch(url);
    if (!response.ok) return null;
    const data = await response.json();

    if (data.retCode !== 0 || !data.result?.list?.length) return null;

    const ticker = data.result.list[0];
    const fundingRate = parseFloat(ticker.fundingRate || '0') * 100;
    const markPrice = parseFloat(ticker.markPrice || '0');
    const openInterest = parseFloat(ticker.openInterest || '0') * markPrice;

    return {
      venue: 'bybit',
      market,
      funding_rate: fundingRate,
      time_to_next: calculateTimeToNextFunding(),
      open_interest: openInterest,
      skew: fundingRate !== 0 ? Math.min(Math.max(fundingRate / 0.1, -1.0), 1.0) : 0.0,
      mark_price: markPrice,
      index_price: parseFloat(ticker.indexPrice || '0'),
      timestamp: new Date().toISOString(),
    };
  } catch (error) {
    console.error(`[BYBIT] Error fetching ${market}:`, error);
    return null;
  }
}

async function fetchOkxFunding(market: string): Promise<FundingData | null> {
  try {
    const symbol = market.replace('/', '-').replace(':USDT', '-SWAP');
    const url = `${VENUE_CONFIG.okx.api_url}/api/v5/public/funding-rate?instId=${symbol}`;

    const response = await fetch(url);
    if (!response.ok) return null;
    const data = await response.json();

    if (data.code !== '0' || !data.data?.length) return null;

    const fundingData = data.data[0];
    const fundingRate = parseFloat(fundingData.fundingRate || '0') * 100;

    return {
      venue: 'okx',
      market,
      funding_rate: fundingRate,
      time_to_next: parseInt(fundingData.fundingTime || '0', 10) / 1000 - Date.now() / 1000,
      open_interest: 0, // Would need separate API call
      skew: fundingRate !== 0 ? Math.min(Math.max(fundingRate / 0.1, -1.0), 1.0) : 0.0,
      mark_price: null,
      index_price: null,
      timestamp: new Date().toISOString(),
    };
  } catch (error) {
    console.error(`[OKX] Error fetching ${market}:`, error);
    return null;
  }
}

async function fetchHyperliquidFunding(market: string): Promise<FundingData | null> {
  try {
    // Hyperliquid uses different symbol format
    const symbol = market.split('/')[0]; // BTC/USDT:USDT -> BTC
    const url = `${VENUE_CONFIG.hyperliquid.api_url}/info`;

    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: 'metaAndAssetCtxs' }),
    });

    if (!response.ok) return null;
    const data = await response.json();

    // Find the asset in the response
    const assetIndex = data[0]?.universe?.findIndex((u: any) => u.name === symbol);
    if (assetIndex === -1 || !data[1]) return null;

    const assetCtx = data[1][assetIndex];
    const fundingRate = parseFloat(assetCtx.funding || '0') * 100;

    return {
      venue: 'hyperliquid',
      market,
      funding_rate: fundingRate,
      time_to_next: calculateTimeToNextFunding(),
      open_interest: parseFloat(assetCtx.openInterest || '0'),
      skew: fundingRate !== 0 ? Math.min(Math.max(fundingRate / 0.1, -1.0), 1.0) : 0.0,
      mark_price: parseFloat(assetCtx.markPx || '0'),
      index_price: parseFloat(assetCtx.oraclePx || '0'),
      timestamp: new Date().toISOString(),
    };
  } catch (error) {
    console.error(`[HYPERLIQUID] Error fetching ${market}:`, error);
    return null;
  }
}

async function fetchFundingData(venueIds: string[], markets: string[]): Promise<FundingData[]> {
  const tasks: Promise<FundingData | null>[] = [];

  for (const venueId of venueIds) {
    if (!getSupportedVenues().includes(venueId)) {
      console.warn(`[FETCH] Venue ${venueId} not supported`);
      continue;
    }

    for (const market of markets) {
      if (venueId === 'binance') {
        tasks.push(fetchBinanceFunding(market));
      } else if (venueId === 'bybit') {
        tasks.push(fetchBybitFunding(market));
      } else if (venueId === 'okx') {
        tasks.push(fetchOkxFunding(market));
      } else if (venueId === 'hyperliquid') {
        tasks.push(fetchHyperliquidFunding(market));
      }
    }
  }

  const results = await Promise.allSettled(tasks);
  return results
    .filter((r): r is PromiseFulfilledResult<FundingData> => r.status === 'fulfilled' && r.value !== null)
    .map(r => r.value);
}

console.log('[STARTUP] Exchange API configuration complete ✓');

// ============================================
// STEP 3: Create Agent App
// ============================================
console.log('[STARTUP] Step 3: Creating agent app...');

const app = createAgentApp({
  name: 'Perps Funding Pulse',
  description: 'Real-time perpetual futures funding rates across major exchanges',
  version: '1.0.0',
  paymentsConfig: {
    facilitatorUrl: FACILITATOR_URL,
    address: WALLET_ADDRESS as `0x${string}`,
    network: NETWORK,
    defaultPrice: DEFAULT_PRICE,
  },
});

console.log('[STARTUP] Agent app created ✓');

const honoApp = app.app;

// ============================================
// STEP 4: Define Entrypoints
// ============================================
console.log('[STARTUP] Step 4: Defining entrypoints...');

// Health check
honoApp.get('/health', (c) => {
  console.log('[HEALTH] Health check requested');
  return c.json({
    status: 'ok',
    timestamp: new Date().toISOString(),
    service: 'Perps Funding Pulse',
    version: '1.0.0',
    supported_venues: getSupportedVenues(),
  });
});

// Venues list
honoApp.get('/venues', (c) => {
  const venues = getSupportedVenues();
  return c.json({
    venues,
    total: venues.length,
  });
});

// OG Image endpoint
honoApp.get('/og-image.png', (c) => {
  const svg = `<svg width="1200" height="630" xmlns="http://www.w3.org/2000/svg">
  <rect width="1200" height="630" fill="#1a0a2e"/>
  <text x="600" y="280" font-family="Arial" font-size="60" fill="#ffbf00" text-anchor="middle" font-weight="bold">Perps Funding Pulse</text>
  <text x="600" y="350" font-family="Arial" font-size="32" fill="#ffd89c" text-anchor="middle">Real-Time Perpetual Futures Funding Rates</text>
  <text x="600" y="420" font-family="Arial" font-size="24" fill="#b8c5d6" text-anchor="middle">Binance · Bybit · OKX · Hyperliquid</text>
  <text x="600" y="500" font-family="Arial" font-size="20" fill="#80cbc4" text-anchor="middle">x402 Payment Protocol</text>
</svg>`;
  c.header('Content-Type', 'image/svg+xml');
  return c.body(svg);
});

// Register agent-kit entrypoint
app.addEntrypoint({
  key: 'perps-funding-pulse',
  name: 'Perps Funding Pulse',
  description: 'Get current funding rates, time to next payment, and open interest for perpetual markets',
  price: '$0.05',
  outputSchema: {
    input: {
      type: 'http',
      method: 'POST',
      discoverable: true,
      bodyType: 'json',
      bodyFields: {
        venue_ids: {
          type: 'array',
          required: true,
          description: 'Perpetual exchanges to query (e.g., ["binance", "bybit", "okx"])',
        },
        markets: {
          type: 'array',
          required: true,
          description: 'Specific markets to track (e.g., ["BTC/USDT:USDT", "ETH/USDT:USDT"])',
        },
      },
    },
    output: {
      type: 'object',
      description: 'Funding rate data with venue-specific metrics',
      required: ['total_markets', 'markets', 'timestamp'],
      properties: {
        total_markets: { type: 'integer', description: 'Number of markets returned' },
        markets: {
          type: 'array',
          description: 'Funding data for each market',
          items: {
            type: 'object',
            properties: {
              venue: { type: 'string', description: 'Exchange name' },
              market: { type: 'string', description: 'Market symbol' },
              funding_rate: { type: 'number', description: 'Current funding rate (% per 8h)' },
              time_to_next: { type: 'integer', description: 'Seconds until next funding' },
              open_interest: { type: 'number', description: 'Total open interest in USD' },
              skew: { type: ['number', 'null'], description: 'Long/short skew ratio' },
              mark_price: { type: ['number', 'null'], description: 'Current mark price' },
              index_price: { type: ['number', 'null'], description: 'Current index price' },
              timestamp: { type: 'string', description: 'Data timestamp' },
            },
          },
        },
        timestamp: { type: 'string', description: 'Response timestamp' },
      },
    },
  } as any,
  handler: async (ctx) => {
    console.log('[AGENT-KIT] perps-funding-pulse handler called');
    const input = ctx.input as { venue_ids: string[]; markets: string[] };

    const supportedVenues = getSupportedVenues();
    const invalidVenues = input.venue_ids.filter(v => !supportedVenues.includes(v));

    if (invalidVenues.length > 0) {
      throw new Error(`Venues not supported: ${invalidVenues.join(', ')}. Available: ${supportedVenues.join(', ')}`);
    }

    const fundingData = await fetchFundingData(input.venue_ids, input.markets);

    if (fundingData.length === 0) {
      throw new Error('Failed to fetch funding data from any venue');
    }

    return {
      total_markets: fundingData.length,
      markets: fundingData,
      timestamp: new Date().toISOString(),
    };
  },
});

console.log('[STARTUP] Agent-kit entrypoint registered ✓');

// ============================================
// STEP 5: Create Wrapper App for OG Metadata
// ============================================
console.log('[STARTUP] Step 5: Creating wrapper app with custom root HTML...');

const wrapperApp = new Hono();

// Favicon
wrapperApp.get('/favicon.ico', (c) => {
  console.log('[WRAPPER] ✓ Serving favicon');
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" fill="#ffbf00"/>
    <text y=".9em" x="50%" text-anchor="middle" font-size="90">📊</text>
  </svg>`;
  c.header('Content-Type', 'image/svg+xml');
  return c.body(svg);
});

// Root route with OG metadata
wrapperApp.get('/', (c) => {
  console.log('[WRAPPER] ✓ Serving custom root HTML with OG tags');
  return c.html(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Perps Funding Pulse - x402 Agent</title>
  <meta name="description" content="Real-time perpetual futures funding rates across major exchanges via x402 micropayments">
  <link rel="icon" type="image/svg+xml" href="/favicon.ico">

  <!-- CRITICAL: Open Graph tags for x402scan validation -->
  <meta property="og:type" content="website">
  <meta property="og:url" content="https://perps-funding-pulse-production.up.railway.app/">
  <meta property="og:title" content="Perps Funding Pulse - x402 Agent">
  <meta property="og:description" content="Real-time perpetual futures funding rates across major exchanges via x402 micropayments">
  <meta property="og:image" content="https://perps-funding-pulse-production.up.railway.app/og-image.png">

  <!-- Twitter tags -->
  <meta property="twitter:card" content="summary_large_image">
  <meta property="twitter:url" content="https://perps-funding-pulse-production.up.railway.app/">
  <meta property="twitter:title" content="Perps Funding Pulse - x402 Agent">
  <meta property="twitter:description" content="Real-time perpetual futures funding rates across major exchanges via x402 micropayments">
  <meta property="twitter:image" content="https://perps-funding-pulse-production.up.railway.app/og-image.png">

  <style>
    body { font-family: system-ui; max-width: 1200px; margin: 40px auto; padding: 20px; background: #1a0a2e; color: #e8f0f2; }
    h1 { color: #ffbf00; }
    h2 { color: #ffbf00; border-bottom: 2px solid rgba(255, 191, 0, 0.3); padding-bottom: 10px; }
    .endpoint { background: rgba(26, 10, 46, 0.6); padding: 15px; border-radius: 8px; margin: 10px 0; border-left: 4px solid #ffbf00; }
    code { background: rgba(0, 0, 0, 0.3); color: #a5d6a7; padding: 2px 6px; border-radius: 4px; }
    .badge { display: inline-block; background: rgba(255, 191, 0, 0.2); border: 1px solid rgba(255, 191, 0, 0.4); color: #ffbf00; padding: 6px 14px; border-radius: 20px; margin-right: 10px; }
  </style>
</head>
<body>
  <h1>Perps Funding Pulse</h1>
  <p>Real-time perpetual futures funding rates across major exchanges</p>

  <div style="margin: 20px 0;">
    <span class="badge">Live</span>
    <span class="badge">4 Venues</span>
    <span class="badge">x402 Payments</span>
  </div>

  <h2>x402 Agent Endpoints</h2>
  <div class="endpoint">
    <strong>Invoke:</strong> <code>POST /entrypoints/perps-funding-pulse/invoke</code>
  </div>
  <div class="endpoint">
    <strong>Agent Discovery:</strong> <code>GET /.well-known/agent.json</code>
  </div>
  <div class="endpoint">
    <strong>Health:</strong> <code>GET /health</code>
  </div>
  <div class="endpoint">
    <strong>Venues:</strong> <code>GET /venues</code>
  </div>

  <h2>Supported Venues</h2>
  <p>Binance Futures, Bybit, OKX, Hyperliquid</p>

  <h2>Pricing</h2>
  <p><strong>$0.05 USDC</strong> per request on Base network</p>

  <p style="margin-top: 40px; opacity: 0.7;"><small>Powered by agent-kit + x402</small></p>
</body>
</html>`);
});

// Forward all other requests to agent-kit
wrapperApp.all('*', async (c) => {
  console.log(`[WRAPPER] Forwarding ${c.req.method} ${c.req.path} to agent-kit`);
  return honoApp.fetch(c.req.raw);
});

console.log('[STARTUP] Wrapper app created - will intercept root route with OG metadata ✓');

// ============================================
// STEP 6: Start Server
// ============================================
console.log('[STARTUP] Step 6: Starting server...');

const isBun = typeof Bun !== 'undefined';
console.log(`[CONFIG] Detected runtime: ${isBun ? 'Bun' : 'Node.js'}`);

if (isBun) {
  Bun.serve({
    port: PORT,
    hostname: HOST,
    fetch: wrapperApp.fetch,
  });
  console.log(`[SUCCESS] ✓ Server running at http://${HOST}:${PORT} (Bun)`);
} else {
  const { serve } = await import('@hono/node-server');
  serve({
    fetch: wrapperApp.fetch,
    port: PORT,
    hostname: HOST,
  }, (info) => {
    console.log(`[SUCCESS] ✓ Server running at http://${info.address}:${info.port} (Node.js)`);
  });
}

console.log(`[SUCCESS] ✓ Health check: http://${HOST}:${PORT}/health`);
console.log(`[SUCCESS] ✓ Entrypoints: http://${HOST}:${PORT}/entrypoints`);
console.log('[SUCCESS] ===== READY TO ACCEPT REQUESTS =====');
