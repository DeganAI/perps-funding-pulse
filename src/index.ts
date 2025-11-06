import { createAgentApp } from "@lucid-agents/agent-kit";
import { Hono } from "hono";
import { z } from "zod";

// Input schema
const FundingInputSchema = z.object({
  venue_ids: z.array(z.string()).describe("Perpetual exchanges to query (e.g., ['binance', 'bybit', 'okx', 'hyperliquid'])"),
  markets: z.array(z.string()).describe("Specific markets to track (e.g., ['BTC/USDT:USDT', 'ETH/USDT:USDT'])"),
});

// Output schema
const FundingOutputSchema = z.object({
  total_markets: z.number(),
  markets: z.array(z.object({
    venue: z.string(),
    market: z.string(),
    funding_rate: z.number(),
    time_to_next: z.number(),
    open_interest: z.number(),
    skew: z.number().nullable(),
    mark_price: z.number().nullable(),
    index_price: z.number().nullable(),
    timestamp: z.string(),
  })),
  timestamp: z.string(),
});

const { app, addEntrypoint, config } = createAgentApp(
  {
    name: "Perps Funding Pulse",
    version: "1.0.0",
    description: "Real-time perpetual futures funding rates across major exchanges",
  },
  {
    config: {
      payments: {
        facilitatorUrl: "https://facilitator.daydreams.systems",
        payTo: "0x01D11F7e1a46AbFC6092d7be484895D2d505095c",
        network: "base",
        asset: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        defaultPrice: "$0.05", // 0.05 USDC
      },
    },
    useConfigPayments: true,
    ap2: {
      required: true,
      params: { roles: ["merchant"] },
    },
  }
);

// Venue configuration
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

async function fetchBinanceFunding(market: string) {
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

async function fetchBybitFunding(market: string) {
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

async function fetchOkxFunding(market: string) {
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
      open_interest: 0,
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

async function fetchHyperliquidFunding(market: string) {
  try {
    const symbol = market.split('/')[0];
    const url = `${VENUE_CONFIG.hyperliquid.api_url}/info`;

    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type: 'metaAndAssetCtxs' }),
    });

    if (!response.ok) return null;
    const data = await response.json();

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

async function fetchFundingData(venueIds: string[], markets: string[]) {
  const tasks: Promise<any>[] = [];

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
    .filter((r): r is PromiseFulfilledResult<any> => r.status === 'fulfilled' && r.value !== null)
    .map(r => r.value);
}

// Register entrypoint
addEntrypoint({
  key: "perps-funding-pulse",
  description: "Get current funding rates, time to next payment, and open interest for perpetual markets",
  input: FundingInputSchema,
  output: FundingOutputSchema,
  price: "$0.05", // 0.05 USDC
  async handler({ input }) {
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
      output: {
        total_markets: fundingData.length,
        markets: fundingData,
        timestamp: new Date().toISOString(),
      },
    };
  },
});

// Create wrapper app for internal API
const wrapperApp = new Hono();

// Internal API endpoint (no payment required)
wrapperApp.post("/api/internal/perps-funding-pulse", async (c) => {
  try {
    // Check API key authentication
    const apiKey = c.req.header("X-Internal-API-Key");
    const expectedKey = process.env.INTERNAL_API_KEY;

    if (!expectedKey) {
      console.error("[INTERNAL API] INTERNAL_API_KEY not set");
      return c.json({ error: "Server configuration error" }, 500);
    }

    if (apiKey !== expectedKey) {
      return c.json({ error: "Unauthorized" }, 401);
    }

    // Get input from request body
    const input = await c.req.json();

    // Validate input
    const validatedInput = FundingInputSchema.parse(input);

    // Call the same logic as x402 endpoint
    const supportedVenues = getSupportedVenues();
    const invalidVenues = validatedInput.venue_ids.filter(v => !supportedVenues.includes(v));

    if (invalidVenues.length > 0) {
      return c.json({
        error: `Venues not supported: ${invalidVenues.join(', ')}. Available: ${supportedVenues.join(', ')}`
      }, 400);
    }

    const fundingData = await fetchFundingData(validatedInput.venue_ids, validatedInput.markets);

    if (fundingData.length === 0) {
      return c.json({ error: 'Failed to fetch funding data from any venue' }, 500);
    }

    return c.json({
      total_markets: fundingData.length,
      markets: fundingData,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    console.error("[INTERNAL API] Error:", error);
    return c.json({ error: error instanceof Error ? error.message : "Internal error" }, 500);
  }
});

// Mount the x402 agent app (public, requires payment)
wrapperApp.route("/", app);

// Export for Bun
export default {
  port: parseInt(process.env.PORT || '3000'),
  fetch: wrapperApp.fetch,
};

console.log(`🚀 Perps Funding Pulse running on port ${process.env.PORT || 3000}`);
console.log(`📝 Manifest: ${process.env.BASE_URL}/.well-known/agent.json`);
console.log(`💰 Payment address: ${config.payments?.payTo}`);
console.log(`🔓 Internal API: /api/internal/perps-funding-pulse (requires API key)`);
