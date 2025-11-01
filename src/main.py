"""
Perps Funding Pulse - Real-time perpetual futures funding rate tracker

x402 micropayment-enabled funding rate oracle for perpetual markets
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import os
import logging
from datetime import datetime

from src.perps_fetcher import PerpsFetcher
from src.x402_middleware_dual import X402Middleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="Perps Funding Pulse",
    description="Real-time perpetual futures funding rates across major exchanges - powered by x402",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configuration
payment_address = os.getenv("PAYMENT_ADDRESS", "0x01D11F7e1a46AbFC6092d7be484895D2d505095c")
base_url = os.getenv("BASE_URL", "https://perps-funding-pulse-production.up.railway.app")
free_mode = os.getenv("FREE_MODE", "false").lower() == "true"

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# x402 Payment Verification Middleware (Dual Facilitator)
app.add_middleware(
    X402Middleware,
    payment_address=payment_address,
    base_url=base_url,
    facilitator_urls=[
        "https://facilitator.daydreams.systems",
        "https://api.cdp.coinbase.com/platform/v2/x402/facilitator"
    ],
    free_mode=free_mode,
)

if not free_mode:
    logger.info("x402 payment verification enabled")
else:
    logger.warning("Running in FREE MODE - no payment verification")

# Initialize Perps Fetcher
perps_fetcher = PerpsFetcher()
logger.info("Perps fetcher initialized")

# Mount static files (if they exist)
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception:
    logger.warning("Static files directory not found")


# Request/Response Models
class FundingRequest(BaseModel):
    """Request for funding rate data"""

    venue_ids: List[str] = Field(
        ...,
        description="Perpetual exchanges to query (e.g., ['binance', 'bybit', 'okx'])",
        example=["binance", "bybit", "okx", "hyperliquid"],
    )
    markets: List[str] = Field(
        ...,
        description="Specific markets to track (e.g., ['BTC/USDT:USDT', 'ETH/USDT:USDT'])",
        example=["BTC/USDT:USDT", "ETH/USDT:USDT"],
    )


class MarketFundingData(BaseModel):
    """Funding data for a single market"""

    venue: str
    market: str
    funding_rate: float = Field(description="Current funding rate (% per 8h)")
    time_to_next: int = Field(description="Seconds until next funding payment")
    open_interest: float = Field(description="Total open interest in USD")
    skew: Optional[float] = Field(None, description="Long/short skew ratio (-1 to 1)")
    mark_price: Optional[float] = Field(None, description="Current mark price")
    index_price: Optional[float] = Field(None, description="Current index price")
    timestamp: str


class FundingResponse(BaseModel):
    """Response with funding rate data"""

    total_markets: int
    markets: List[MarketFundingData]
    timestamp: str


# Endpoints
@app.get("/", response_class=HTMLResponse)
@app.head("/")
async def root():
    """Landing page"""
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Perps Funding Pulse - Real-Time Funding Rates</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #1a0a2e 0%, #16213e 50%, #0f3460 100%);
                color: #e8f0f2;
                line-height: 1.6;
                min-height: 100vh;
            }}
            .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
            header {{
                background: linear-gradient(135deg, rgba(255, 191, 0, 0.15) 0%, rgba(255, 107, 107, 0.15) 100%);
                border: 2px solid rgba(255, 191, 0, 0.3);
                border-radius: 16px;
                padding: 40px;
                margin-bottom: 30px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            }}
            h1 {{
                color: #ffbf00;
                font-size: 2.5em;
                margin-bottom: 10px;
                text-shadow: 0 2px 8px rgba(255, 191, 0, 0.3);
            }}
            .subtitle {{
                color: #ffd89c;
                font-size: 1.2em;
                margin-bottom: 15px;
            }}
            .badge {{
                display: inline-block;
                background: rgba(255, 191, 0, 0.2);
                border: 1px solid rgba(255, 191, 0, 0.4);
                color: #ffbf00;
                padding: 6px 14px;
                border-radius: 20px;
                font-size: 0.9em;
                margin-right: 10px;
                margin-top: 10px;
                font-weight: 600;
            }}
            .section {{
                background: rgba(22, 33, 62, 0.8);
                border: 1px solid rgba(255, 191, 0, 0.1);
                border-radius: 12px;
                padding: 30px;
                margin-bottom: 25px;
                box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
            }}
            h2 {{
                color: #ffbf00;
                margin-bottom: 20px;
                font-size: 1.8em;
                border-bottom: 2px solid rgba(255, 191, 0, 0.3);
                padding-bottom: 10px;
            }}
            h3 {{
                color: #ffd89c;
                margin: 15px 0 10px 0;
                font-size: 1.3em;
            }}
            .endpoint {{
                background: rgba(26, 10, 46, 0.6);
                border-left: 4px solid #ffbf00;
                padding: 20px;
                margin: 20px 0;
                border-radius: 8px;
                transition: all 0.3s ease;
            }}
            .endpoint:hover {{
                transform: translateX(4px);
                border-left-color: #ff6b6b;
                box-shadow: 0 4px 12px rgba(255, 191, 0, 0.15);
            }}
            .method {{
                display: inline-block;
                background: linear-gradient(135deg, #ffbf00 0%, #ff9500 100%);
                color: #1a0a2e;
                padding: 4px 12px;
                border-radius: 4px;
                font-weight: 700;
                font-size: 0.85em;
                margin-right: 10px;
            }}
            .method.get {{ background: linear-gradient(135deg, #6BCF7F 0%, #4CAF50 100%); color: white; }}
            code {{
                background: rgba(0, 0, 0, 0.3);
                color: #a5d6a7;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
                font-size: 0.9em;
            }}
            pre {{
                background: rgba(0, 0, 0, 0.5);
                border: 1px solid rgba(77, 182, 172, 0.2);
                border-radius: 6px;
                padding: 15px;
                overflow-x: auto;
                margin: 10px 0;
            }}
            pre code {{
                background: none;
                padding: 0;
                display: block;
                color: #a5d6a7;
            }}
            .grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                gap: 15px;
                margin: 15px 0;
            }}
            .card {{
                background: rgba(26, 10, 46, 0.6);
                border: 1px solid rgba(255, 191, 0, 0.2);
                border-radius: 10px;
                padding: 20px;
                transition: all 0.3s ease;
            }}
            .card:hover {{
                transform: translateY(-3px);
                border-color: rgba(255, 191, 0, 0.4);
                box-shadow: 0 6px 20px rgba(255, 191, 0, 0.1);
            }}
            .card h4 {{
                color: #ffbf00;
                margin-bottom: 10px;
                font-size: 1.2em;
            }}
            .highlight {{
                color: #ffbf00;
                font-weight: bold;
            }}
            a {{
                color: #ffbf00;
                text-decoration: none;
                border-bottom: 1px solid transparent;
                transition: all 0.3s ease;
            }}
            a:hover {{
                border-bottom-color: #ffbf00;
            }}
            footer {{
                text-align: center;
                padding: 30px 20px;
                color: #80cbc4;
                opacity: 0.8;
            }}
            .status-indicator {{
                display: inline-block;
                width: 8px;
                height: 8px;
                background: #4caf50;
                border-radius: 50%;
                margin-right: 6px;
                animation: pulse 2s infinite;
            }}
            @keyframes pulse {{
                0%, 100% {{ opacity: 1; }}
                50% {{ opacity: 0.5; }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>Perps Funding Pulse</h1>
                <p class="subtitle">Real-Time Perpetual Futures Funding Rates</p>
                <p style="font-size: 0.95em; color: #b8c5d6; margin: 10px 0 15px 0;">Track funding rates, open interest, and market skew across major perpetuals exchanges</p>
                <div>
                    <span class="badge"><span class="status-indicator"></span>Live</span>
                    <span class="badge">6+ Venues</span>
                    <span class="badge">Real-time Updates</span>
                    <span class="badge">x402 Payments</span>
                </div>
            </header>

            <div class="section">
                <h2>What is Perps Funding Pulse?</h2>
                <p style="font-size: 1.05em; line-height: 1.7; margin-top: 12px;">
                    Perps Funding Pulse provides real-time funding rate data for perpetual futures contracts across <span class="highlight">Binance Futures, Bybit, OKX, Hyperliquid, dYdX, and GMX</span>. Track funding rates, open interest, and long/short skew to make informed trading decisions.
                </p>

                <div class="grid" style="margin-top: 25px;">
                    <div class="card">
                        <h4>Real-Time Rates</h4>
                        <p>Current funding rates updated every minute from major perpetuals exchanges.</p>
                    </div>
                    <div class="card">
                        <h4>Open Interest</h4>
                        <p>Track total open interest in USD to gauge market positioning and liquidity.</p>
                    </div>
                    <div class="card">
                        <h4>Market Skew</h4>
                        <p>Monitor long/short skew ratios to identify imbalanced markets and opportunities.</p>
                    </div>
                    <div class="card">
                        <h4>Multi-Venue</h4>
                        <p>Compare funding rates across CEX (Binance, Bybit, OKX) and DEX (dYdX, GMX, Hyperliquid).</p>
                    </div>
                </div>
            </div>

            <div class="section">
                <h2>API Endpoints</h2>

                <div class="endpoint">
                    <h3><span class="method">POST</span>/perps/funding</h3>
                    <p>Get current funding rates, next payment time, and open interest for specified markets</p>
                    <pre><code>curl -X POST https://perps-funding-pulse.up.railway.app/perps/funding \\
  -H "Content-Type: application/json" \\
  -d '{{
    "venue_ids": ["binance", "bybit", "okx"],
    "markets": ["BTC/USDT:USDT", "ETH/USDT:USDT"]
  }}'</code></pre>
                </div>

                <div class="endpoint">
                    <h3><span class="method">POST</span>/entrypoints/perps-funding-pulse/invoke</h3>
                    <p>AP2-compatible entrypoint for funding data (x402 payment required in production)</p>
                </div>

                <div class="endpoint">
                    <h3><span class="method get">GET</span>/venues</h3>
                    <p>List all supported perpetuals exchanges and their status</p>
                </div>

                <div class="endpoint">
                    <h3><span class="method get">GET</span>/health</h3>
                    <p>Health check and operational status</p>
                </div>
            </div>

            <div class="section">
                <h2>x402 Micropayments</h2>
                <p style="margin-bottom: 15px;">
                    Perps Funding Pulse uses the <strong>x402 payment protocol</strong> for usage-based billing.
                </p>

                <div class="grid">
                    <div class="card">
                        <h4>Payment Details</h4>
                        <p><strong>Price:</strong> 0.05 USDC per request</p>
                        <p><strong>Address:</strong> <code style="word-break: break-all;">{payment_address}</code></p>
                        <p><strong>Network:</strong> Base</p>
                    </div>
                    <div class="card">
                        <h4>How to Pay</h4>
                        <p>Payments processed via daydreams facilitator</p>
                        <p style="margin-top: 8px;"><em>{"Currently in FREE MODE for testing" if free_mode else "Payment verification active"}</em></p>
                    </div>
                </div>
            </div>

            <div class="section">
                <h2>Supported Venues</h2>
                <div class="grid">
                    <div class="card"><h4>Binance Futures</h4><p>USDT-margined perpetuals</p></div>
                    <div class="card"><h4>Bybit</h4><p>Unified trading account</p></div>
                    <div class="card"><h4>OKX</h4><p>Perpetual swaps</p></div>
                    <div class="card"><h4>Hyperliquid</h4><p>L1 perpetuals DEX</p></div>
                    <div class="card"><h4>dYdX</h4><p>Decentralized perpetuals</p></div>
                    <div class="card"><h4>GMX</h4><p>Decentralized leverage trading</p></div>
                </div>
            </div>

            <div class="section">
                <h2>Documentation</h2>
                <p style="margin-bottom: 15px;">Interactive API documentation available:</p>
                <div style="margin: 15px 0;">
                    <a href="/docs" style="display: inline-block; background: rgba(77, 182, 172, 0.2); padding: 10px 20px; border-radius: 5px; border: 1px solid #4db6ac; margin-right: 12px;">Swagger UI</a>
                    <a href="/redoc" style="display: inline-block; background: rgba(77, 182, 172, 0.2); padding: 10px 20px; border-radius: 5px; border: 1px solid #4db6ac;">ReDoc</a>
                </div>
            </div>

            <footer>
                <p><strong>Built by DeganAI</strong></p>
                <p style="margin-top: 8px; opacity: 0.7;">Bounty #8 Submission for Daydreams AI Agent Bounties</p>
            </footer>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/.well-known/agent.json")
@app.head("/.well-known/agent.json")
async def agent_metadata():
    """AP2 (Agent Payments Protocol) metadata - returns HTTP 200"""
    agent_json = {
        "name": "Perps Funding Pulse",
        "description": "Real-time perpetual futures funding rates, open interest, and market skew across major exchanges (Binance, Bybit, OKX, Hyperliquid, dYdX, GMX)",
        "url": base_url.replace("https://", "http://") + "/",
        "version": "1.0.0",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": True,
            "extensions": [
                {
                    "uri": "https://github.com/google-agentic-commerce/ap2/tree/v0.1",
                    "description": "Agent Payments Protocol (AP2)",
                    "required": True,
                    "params": {
                        "roles": ["merchant"]
                    }
                }
            ]
        },
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json", "text/plain"],
        "skills": [
            {
                "id": "perps-funding-pulse",
                "name": "perps-funding-pulse",
                "description": "Get current funding rates, time to next payment, and open interest for perpetual markets",
                "inputModes": ["application/json"],
                "outputModes": ["application/json"],
                "streaming": False,
                "x_input_schema": {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "type": "object",
                    "properties": {
                        "venue_ids": {
                            "description": "Perpetual exchanges to query",
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1
                        },
                        "markets": {
                            "description": "Specific markets to track (CCXT format)",
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1
                        }
                    },
                    "required": ["venue_ids", "markets"],
                    "additionalProperties": False
                },
                "x_output_schema": {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "type": "object",
                    "properties": {
                        "total_markets": {"type": "integer"},
                        "markets": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "venue": {"type": "string"},
                                    "market": {"type": "string"},
                                    "funding_rate": {"type": "number"},
                                    "time_to_next": {"type": "integer"},
                                    "open_interest": {"type": "number"},
                                    "skew": {"type": "number"}
                                }
                            }
                        },
                        "timestamp": {"type": "string"}
                    },
                    "required": ["total_markets", "markets", "timestamp"],
                    "additionalProperties": False
                }
            }
        ],
        "supportsAuthenticatedExtendedCard": False,
        "entrypoints": {
            "perps-funding-pulse": {
                "description": "Get current funding rates and open interest for perpetual markets",
                "streaming": False,
                "input_schema": {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "type": "object",
                    "properties": {
                        "venue_ids": {
                            "description": "Exchanges to query",
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1
                        },
                        "markets": {
                            "description": "Markets to track",
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1
                        }
                    },
                    "required": ["venue_ids", "markets"],
                    "additionalProperties": False
                },
                "output_schema": {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "type": "object",
                    "properties": {
                        "total_markets": {"type": "integer"},
                        "markets": {"type": "array"},
                        "timestamp": {"type": "string"}
                    },
                    "additionalProperties": False
                },
                "pricing": {
                    "invoke": "0.05 USDC"
                }
            }
        },
        "payments": [
            {
                "method": "x402",
                "payee": payment_address,
                "network": "base",
                "endpoint": "https://facilitator.daydreams.systems",
                "priceModel": {
                    "default": "0.05"
                },
                "extensions": {
                    "x402": {
                        "facilitatorUrl": "https://facilitator.daydreams.systems"
                    }
                }
            }
        ]
    }

    return JSONResponse(content=agent_json, status_code=200)


@app.get("/.well-known/x402")
@app.head("/.well-known/x402")
async def x402_metadata():
    """x402 protocol metadata for service discovery"""
    metadata = {
        "x402Version": 1,
        "accepts": [
            {
                "scheme": "exact",
                "network": "base",
                "maxAmountRequired": "50000",  # 0.05 USDC (6 decimals)
                "resource": f"{base_url}/entrypoints/perps-funding-pulse/invoke",
                "description": "Get real-time perpetual funding rates, open interest, and market skew",
                "mimeType": "application/json",
                "payTo": payment_address,
                "maxTimeoutSeconds": 30,
                "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # USDC on Base
                "outputSchema": {
                    "input": {
                        "type": "http",
                        "method": "POST",
                        "bodyType": "json",
                        "bodyFields": {
                            "venue_ids": {
                                "type": "array",
                                "required": True,
                                "description": "Exchanges to query (e.g., ['binance', 'bybit', 'okx'])"
                            },
                            "markets": {
                                "type": "array",
                                "required": True,
                                "description": "Markets to track (e.g., ['BTC-PERP', 'ETH-PERP'])"
                            }
                        }
                    },
                    "output": {
                        "type": "object",
                        "properties": {
                            "total_markets": {"type": "integer"},
                            "markets": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "venue": {"type": "string"},
                                        "market": {"type": "string"},
                                        "funding_rate": {"type": "number"},
                                        "next_funding_time": {"type": "string"},
                                        "open_interest": {"type": "number"}
                                    }
                                }
                            },
                            "timestamp": {"type": "string"}
                        }
                    }
                },
                "extra": {
                    "supported_venues": ["Binance", "Bybit", "OKX", "Hyperliquid"],
                    "features": ["real-time funding rates", "open interest tracking", "next funding time", "market skew analysis"],
                    "accuracy": "Live data from exchange APIs"
                }
            }
        ]
    }

    return JSONResponse(content=metadata, status_code=200)


@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "service": "perps-funding-pulse",
        "version": "1.0.0",
        "free_mode": free_mode,
        "supported_venues": perps_fetcher.get_supported_venues(),
    }


@app.get("/venues")
async def list_venues():
    """List all supported venues"""
    venues = perps_fetcher.get_supported_venues()
    return {
        "venues": venues,
        "total": len(venues),
    }


@app.post("/perps/funding", response_model=FundingResponse)
async def get_funding_data(request: FundingRequest):
    """
    Get current funding rates and open interest

    Fetches real-time funding rate data from specified perpetual exchanges
    including current rates, time until next payment, open interest, and skew.
    """
    try:
        # Validate venue IDs
        supported_venues = perps_fetcher.get_supported_venues()
        invalid_venues = [v for v in request.venue_ids if v not in supported_venues]

        if invalid_venues:
            raise HTTPException(
                status_code=400,
                detail=f"Venues not supported: {invalid_venues}. Available: {supported_venues}",
            )

        # Fetch funding data
        logger.info(f"Fetching funding data for venues: {request.venue_ids}, markets: {request.markets}")
        funding_data = await perps_fetcher.fetch_funding_data(
            venue_ids=request.venue_ids,
            markets=request.markets
        )

        if not funding_data:
            raise HTTPException(
                status_code=503,
                detail="Failed to fetch funding data from any venue",
            )

        # Build response
        market_results = []
        for data in funding_data:
            market_results.append(
                MarketFundingData(
                    venue=data["venue"],
                    market=data["market"],
                    funding_rate=round(data["funding_rate"], 6),
                    time_to_next=data["time_to_next"],
                    open_interest=round(data["open_interest"], 2),
                    skew=round(data["skew"], 4) if data.get("skew") is not None else None,
                    mark_price=round(data["mark_price"], 2) if data.get("mark_price") else None,
                    index_price=round(data["index_price"], 2) if data.get("index_price") else None,
                    timestamp=data["timestamp"],
                )
            )

        return FundingResponse(
            total_markets=len(market_results),
            markets=market_results,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Funding data fetch error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


@app.get("/entrypoints/perps-funding-pulse/invoke")
@app.head("/entrypoints/perps-funding-pulse/invoke")
async def entrypoint_perps_funding_get():
    """
    x402 discovery endpoint - returns HTTP 402 with payment requirements
    """
    metadata = {
        "x402Version": 1,
        "accepts": [
            {
                "scheme": "exact",
                "network": "base",
                "maxAmountRequired": "50000",
                "resource": f"{base_url}/entrypoints/perps-funding-pulse/invoke",
                "description": "Fetch current funding rate, next tick, and open interest for perps markets",
                "mimeType": "application/json",
                "payTo": payment_address,
                "maxTimeoutSeconds": 30,
                "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            }
        ]
    }
    return JSONResponse(content=metadata, status_code=402)


@app.post(
    "/entrypoints/perps-funding-pulse/invoke",
    summary="Real-time Perpetual Futures Funding Rates",
    description="Get current funding rates, time to next payment, open interest, and market skew across major perpetual exchanges (Binance, Bybit, OKX, Hyperliquid, dYdX, GMX). Returns accurate funding data updated every 8 hours with <2% variance from exchange APIs.",
    response_description="Funding rate data with venue-specific metrics"
)
async def entrypoint_perps_funding(request: FundingRequest):
    """
    AP2 (Agent Payments Protocol) compatible entrypoint

    Calls the main /perps/funding endpoint with the same logic.
    """
    return await get_funding_data(request)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
