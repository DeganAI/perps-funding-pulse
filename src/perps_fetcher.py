"""
Perps funding data fetcher

Fetches real-time funding rates, open interest, and skew from major perpetual exchanges
"""
import httpx
import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone
import asyncio

logger = logging.getLogger(__name__)

# Supported venues configuration
VENUE_CONFIG = {
    "binance": {
        "name": "Binance Futures",
        "api_url": "https://fapi.binance.com",
        "enabled": True,
    },
    "bybit": {
        "name": "Bybit",
        "api_url": "https://api.bybit.com",
        "enabled": True,
    },
    "okx": {
        "name": "OKX",
        "api_url": "https://www.okx.com",
        "enabled": True,
    },
    "hyperliquid": {
        "name": "Hyperliquid",
        "api_url": "https://api.hyperliquid.xyz",
        "enabled": True,
    },
    "dydx": {
        "name": "dYdX",
        "api_url": "https://api.dydx.exchange",
        "enabled": False,  # Requires special handling
    },
    "gmx": {
        "name": "GMX",
        "api_url": "https://api.gmx.io",
        "enabled": False,  # Requires on-chain data
    },
}


class PerpsFetcher:
    """Fetch perpetual futures funding data from multiple exchanges"""

    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=10.0)

    def get_supported_venues(self) -> List[str]:
        """Get list of supported venue IDs"""
        return [venue_id for venue_id, config in VENUE_CONFIG.items() if config["enabled"]]

    async def fetch_funding_data(
        self, venue_ids: List[str], markets: List[str]
    ) -> List[Dict]:
        """
        Fetch funding data for specified venues and markets

        Args:
            venue_ids: List of exchange IDs (e.g., ['binance', 'bybit'])
            markets: List of market symbols in CCXT format (e.g., ['BTC/USDT:USDT'])

        Returns:
            List of funding data dictionaries
        """
        tasks = []
        for venue_id in venue_ids:
            if venue_id not in VENUE_CONFIG or not VENUE_CONFIG[venue_id]["enabled"]:
                logger.warning(f"Venue {venue_id} not supported or disabled")
                continue

            for market in markets:
                tasks.append(self._fetch_venue_market(venue_id, market))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out errors and None results
        funding_data = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error fetching funding data: {result}")
                continue
            if result:
                funding_data.append(result)

        return funding_data

    async def _fetch_venue_market(self, venue_id: str, market: str) -> Optional[Dict]:
        """Fetch funding data for a specific venue and market"""
        try:
            if venue_id == "binance":
                return await self._fetch_binance(market)
            elif venue_id == "bybit":
                return await self._fetch_bybit(market)
            elif venue_id == "okx":
                return await self._fetch_okx(market)
            elif venue_id == "hyperliquid":
                return await self._fetch_hyperliquid(market)
            else:
                logger.warning(f"No fetcher implemented for {venue_id}")
                return None
        except Exception as e:
            logger.error(f"Error fetching {venue_id} {market}: {e}")
            return None

    async def _fetch_binance(self, market: str) -> Optional[Dict]:
        """
        Fetch funding data from Binance Futures

        API: GET /fapi/v1/premiumIndex
        """
        try:
            # Convert CCXT format to Binance symbol (BTC/USDT:USDT -> BTCUSDT)
            symbol = market.replace("/", "").replace(":USDT", "")

            url = f"{VENUE_CONFIG['binance']['api_url']}/fapi/v1/premiumIndex"
            params = {"symbol": symbol}

            response = await self.http_client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # Get open interest
            oi_url = f"{VENUE_CONFIG['binance']['api_url']}/fapi/v1/openInterest"
            oi_response = await self.http_client.get(oi_url, params=params)
            oi_data = oi_response.json() if oi_response.status_code == 200 else {}

            # Calculate time to next funding (Binance funds every 8 hours at 00:00, 08:00, 16:00 UTC)
            now = datetime.now(timezone.utc)
            current_hour = now.hour
            next_funding_hours = [0, 8, 16]
            next_hour = min([h for h in next_funding_hours if h > current_hour], default=24)
            if next_hour == 24:
                next_hour = 0
                hours_until = (24 - current_hour) + next_hour
            else:
                hours_until = next_hour - current_hour

            time_to_next = hours_until * 3600 - (now.minute * 60 + now.second)

            # Extract funding rate (convert from decimal to %)
            funding_rate = float(data.get("lastFundingRate", 0)) * 100

            # Calculate skew (approximate from funding rate sign)
            # Positive rate = longs pay shorts = more longs
            skew = min(max(funding_rate / 0.1, -1.0), 1.0) if funding_rate != 0 else 0.0

            return {
                "venue": "binance",
                "market": market,
                "funding_rate": funding_rate,
                "time_to_next": max(0, int(time_to_next)),
                "open_interest": float(oi_data.get("openInterest", 0)) * float(data.get("markPrice", 0)),
                "skew": skew,
                "mark_price": float(data.get("markPrice", 0)),
                "index_price": float(data.get("indexPrice", 0)),
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }

        except Exception as e:
            logger.error(f"Binance fetch error for {market}: {e}")
            return None

    async def _fetch_bybit(self, market: str) -> Optional[Dict]:
        """
        Fetch funding data from Bybit

        API: GET /v5/market/tickers
        """
        try:
            # Convert CCXT format to Bybit symbol
            symbol = market.replace("/", "").replace(":USDT", "")

            url = f"{VENUE_CONFIG['bybit']['api_url']}/v5/market/tickers"
            params = {"category": "linear", "symbol": symbol}

            response = await self.http_client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("retCode") != 0 or not data.get("result", {}).get("list"):
                return None

            ticker = data["result"]["list"][0]

            # Calculate time to next funding (Bybit funds every 8 hours)
            now = datetime.now(timezone.utc)
            current_hour = now.hour
            next_funding_hours = [0, 8, 16]
            next_hour = min([h for h in next_funding_hours if h > current_hour], default=24)
            if next_hour == 24:
                next_hour = 0
                hours_until = (24 - current_hour) + next_hour
            else:
                hours_until = next_hour - current_hour

            time_to_next = hours_until * 3600 - (now.minute * 60 + now.second)

            # Extract funding rate (convert from decimal to %)
            funding_rate = float(ticker.get("fundingRate", 0)) * 100

            # Calculate skew
            skew = min(max(funding_rate / 0.1, -1.0), 1.0) if funding_rate != 0 else 0.0

            return {
                "venue": "bybit",
                "market": market,
                "funding_rate": funding_rate,
                "time_to_next": max(0, int(time_to_next)),
                "open_interest": float(ticker.get("openInterest", 0)) * float(ticker.get("lastPrice", 0)),
                "skew": skew,
                "mark_price": float(ticker.get("lastPrice", 0)),
                "index_price": float(ticker.get("indexPrice", 0)) if ticker.get("indexPrice") else None,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }

        except Exception as e:
            logger.error(f"Bybit fetch error for {market}: {e}")
            return None

    async def _fetch_okx(self, market: str) -> Optional[Dict]:
        """
        Fetch funding data from OKX

        API: GET /api/v5/public/funding-rate
        """
        try:
            # Convert CCXT format to OKX format (BTC/USDT:USDT -> BTC-USDT-SWAP)
            base_quote = market.split(":")[0]
            base, quote = base_quote.split("/")
            symbol = f"{base}-{quote}-SWAP"

            # Get funding rate
            url = f"{VENUE_CONFIG['okx']['api_url']}/api/v5/public/funding-rate"
            params = {"instId": symbol}

            response = await self.http_client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("code") != "0" or not data.get("data"):
                return None

            funding_data = data["data"][0]

            # Get open interest
            oi_url = f"{VENUE_CONFIG['okx']['api_url']}/api/v5/public/open-interest"
            oi_response = await self.http_client.get(oi_url, params=params)
            oi_data = oi_response.json() if oi_response.status_code == 200 else {}
            oi_value = 0
            if oi_data.get("code") == "0" and oi_data.get("data"):
                oi_value = float(oi_data["data"][0].get("oi", 0))

            # Get mark price
            ticker_url = f"{VENUE_CONFIG['okx']['api_url']}/api/v5/market/ticker"
            ticker_response = await self.http_client.get(ticker_url, params=params)
            ticker_data = ticker_response.json() if ticker_response.status_code == 200 else {}
            mark_price = 0
            if ticker_data.get("code") == "0" and ticker_data.get("data"):
                mark_price = float(ticker_data["data"][0].get("last", 0))

            # Parse next funding time
            next_funding_time = int(funding_data.get("nextFundingTime", 0)) / 1000
            now_timestamp = datetime.now(timezone.utc).timestamp()
            time_to_next = max(0, int(next_funding_time - now_timestamp))

            # Extract funding rate (convert from decimal to %)
            funding_rate = float(funding_data.get("fundingRate", 0)) * 100

            # Calculate skew
            skew = min(max(funding_rate / 0.1, -1.0), 1.0) if funding_rate != 0 else 0.0

            return {
                "venue": "okx",
                "market": market,
                "funding_rate": funding_rate,
                "time_to_next": time_to_next,
                "open_interest": oi_value * mark_price,
                "skew": skew,
                "mark_price": mark_price,
                "index_price": None,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }

        except Exception as e:
            logger.error(f"OKX fetch error for {market}: {e}")
            return None

    async def _fetch_hyperliquid(self, market: str) -> Optional[Dict]:
        """
        Fetch funding data from Hyperliquid

        API: POST /info (meta endpoint)
        """
        try:
            # Convert market format (BTC/USDT:USDT -> BTC)
            base = market.split("/")[0]

            url = f"{VENUE_CONFIG['hyperliquid']['api_url']}/info"

            # Get all markets metadata
            meta_payload = {"type": "meta"}
            response = await self.http_client.post(url, json=meta_payload)
            response.raise_for_status()
            meta_data = response.json()

            # Find the market
            market_info = None
            for universe_item in meta_data.get("universe", []):
                if universe_item.get("name") == base:
                    market_info = universe_item
                    break

            if not market_info:
                logger.warning(f"Market {base} not found in Hyperliquid universe")
                return None

            # Get market state
            state_payload = {"type": "metaAndAssetCtxs"}
            state_response = await self.http_client.post(url, json=state_payload)
            state_data = state_response.json() if state_response.status_code == 200 else []

            # Find market in state data
            market_state = None
            for idx, ctx in enumerate(state_data[1] if len(state_data) > 1 else []):
                if state_data[0]["universe"][idx]["name"] == base:
                    market_state = ctx
                    break

            # Extract funding rate (convert to %)
            funding_rate = float(market_state.get("funding", 0)) * 100 if market_state else 0

            # Hyperliquid funds every hour
            now = datetime.now(timezone.utc)
            minutes_to_next = 60 - now.minute
            time_to_next = minutes_to_next * 60 - now.second

            # Extract open interest
            open_interest = float(market_state.get("openInterest", 0)) if market_state else 0
            mark_price = float(market_state.get("markPx", 0)) if market_state else 0

            # Calculate skew
            skew = min(max(funding_rate / 0.1, -1.0), 1.0) if funding_rate != 0 else 0.0

            return {
                "venue": "hyperliquid",
                "market": market,
                "funding_rate": funding_rate,
                "time_to_next": max(0, int(time_to_next)),
                "open_interest": open_interest * mark_price,
                "skew": skew,
                "mark_price": mark_price,
                "index_price": None,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }

        except Exception as e:
            logger.error(f"Hyperliquid fetch error for {market}: {e}")
            return None

    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()
