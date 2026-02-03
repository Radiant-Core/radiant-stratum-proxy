"""Price tracking from CoinGecko API for Radiant (RXD)"""

import aiohttp
import asyncio
import logging
import time
from typing import Dict, Optional, Tuple

logger = logging.getLogger("PriceTracker")

# CoinGecko API endpoints
COINGECKO_URL = "https://api.coingecko.com/api/v3"
RXD_COINGECKO_ID = "radiant"  # Radiant's CoinGecko ID


class PriceTracker:
    """Tracks Radiant (RXD) cryptocurrency prices from CoinGecko"""

    def __init__(self):
        self.last_rxd_price: Optional[float] = None
        self.last_rxd_price_usd: Optional[float] = None
        self.last_update_time: float = 0
        self.update_interval: float = 3600  # 1 hour (60 * 60 seconds)

        # Block reward caching (same 1-hour interval as prices)
        self.last_rxd_block_reward: Optional[float] = None
        self.last_block_reward_update: float = 0

    async def get_current_prices(self) -> Dict[str, Optional[float]]:
        """
        Fetch current RXD price from CoinGecko with caching.

        Returns cached price if cache is still fresh (< update_interval old).
        Only fetches from API if cache has expired.

        Returns:
            Dictionary with keys: rxd_price, rxd_price_usd, timestamp
        """
        # Check if cache is still fresh
        current_time = time.time()
        if (
            self.last_rxd_price is not None
            and current_time - self.last_update_time < self.update_interval
        ):
            logger.debug(
                f"Using cached prices (age: {current_time - self.last_update_time:.0f}s)"
            )
            return {
                "rxd_price": self.last_rxd_price,
                "rxd_price_usd": self.last_rxd_price_usd,
                "timestamp": int(self.last_update_time),
            }

        # Cache expired or no cache yet, fetch fresh prices
        try:
            async with aiohttp.ClientSession() as session:
                rxd_price, rxd_price_usd = await self._fetch_price(
                    session, RXD_COINGECKO_ID
                )

                # Update cached values
                if rxd_price is not None:
                    self.last_rxd_price = rxd_price
                    self.last_rxd_price_usd = rxd_price_usd

                self.last_update_time = time.time()
                logger.debug(
                    f"Updated price cache: RXD {rxd_price} BTC (${rxd_price_usd} USD)"
                )

                return {
                    "rxd_price": rxd_price,
                    "rxd_price_usd": rxd_price_usd,
                    "timestamp": int(self.last_update_time),
                }
        except Exception as e:
            logger.warning(f"Failed to fetch prices from CoinGecko: {e}")
            # Return cached values on error
            return {
                "rxd_price": self.last_rxd_price,
                "rxd_price_usd": self.last_rxd_price_usd,
                "timestamp": int(self.last_update_time),
            }

    async def _fetch_price(
        self, session: aiohttp.ClientSession, coin_id: str
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Fetch price for a single coin from CoinGecko.

        Args:
            session: aiohttp session
            coin_id: CoinGecko coin ID (e.g., 'radiant')

        Returns:
            Tuple of (BTC price, USD price) or (None, None) on error
        """
        try:
            url = f"{COINGECKO_URL}/simple/price"
            params = {
                "ids": coin_id,
                "vs_currencies": "btc,usd",
                "include_market_cap": "false",
                "include_24hr_vol": "false",
                "include_last_updated_at": "false",
            }

            async with session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if coin_id in data:
                        price_data = data[coin_id]
                        btc_price = price_data.get("btc")
                        usd_price = price_data.get("usd")
                        logger.debug(f"{coin_id}: {btc_price} BTC, ${usd_price} USD")
                        return btc_price, usd_price
                    else:
                        logger.warning(f"CoinGecko response missing {coin_id}")
                        return None, None
                else:
                    logger.warning(f"CoinGecko returned status {resp.status}")
                    return None, None
        except asyncio.TimeoutError:
            logger.warning(f"Timeout fetching price for {coin_id}")
            return None, None
        except Exception as e:
            logger.warning(f"Error fetching price for {coin_id}: {e}")
            return None, None

    async def get_block_rewards(self) -> Dict[str, Optional[float]]:
        """
        Fetch block reward from RXD chain via RPC with caching.

        Returns cached reward if cache is still fresh (< 1 hour old).
        Only fetches from RPC if cache has expired.

        Radiant uses 8 decimal places (1e8) like Bitcoin.

        Returns:
            Dictionary with keys: rxd_block_reward, timestamp
        """
        from ..config import Settings

        current_time = time.time()

        # Check if cache is still fresh
        if (
            self.last_rxd_block_reward is not None
            and current_time - self.last_block_reward_update < self.update_interval
        ):
            logger.debug(
                f"Using cached block reward (age: {current_time - self.last_block_reward_update:.0f}s)"
            )
            return {
                "rxd_block_reward": self.last_rxd_block_reward,
                "timestamp": int(self.last_block_reward_update),
            }

        logger.debug("Fetching block reward from RPC endpoint")
        settings = Settings()
        rxd_reward = 25000.0  # Default fallback (current block reward after first halving)

        try:
            async with aiohttp.ClientSession() as session:
                try:
                    from ..rpc.rxd import getblocktemplate

                    rxd_url = settings.node_url
                    result = await getblocktemplate(session, rxd_url)

                    if result and "result" in result and result["result"]:
                        coinbasevalue = result["result"].get("coinbasevalue", 0)
                        rxd_reward = coinbasevalue / 1e8  # Radiant uses 8 decimal places
                        logger.debug(
                            f"RXD block reward: {rxd_reward} coins (coinbasevalue: {coinbasevalue})"
                        )
                except Exception as e:
                    logger.warning(f"Could not fetch RXD block reward: {e}")

        except Exception as e:
            logger.warning(f"Error fetching block reward: {e}")

        # Cache the result
        self.last_rxd_block_reward = rxd_reward
        self.last_block_reward_update = current_time

        return {
            "rxd_block_reward": rxd_reward,
            "timestamp": int(current_time),
        }

    def get_cached_block_rewards(self) -> Dict[str, Optional[float]]:
        """Get last cached block reward without making RPC calls"""
        return {
            "rxd_block_reward": self.last_rxd_block_reward,
            "timestamp": int(self.last_block_reward_update),
        }

    def get_cached_prices(self) -> Dict[str, Optional[float]]:
        """Get last cached prices without making API call"""
        return {
            "rxd_price": self.last_rxd_price,
            "rxd_price_usd": self.last_rxd_price_usd,
            "timestamp": int(self.last_update_time),
        }


# Global instance
_price_tracker: Optional[PriceTracker] = None


def get_price_tracker() -> PriceTracker:
    """Get or create the global price tracker instance"""
    global _price_tracker
    if _price_tracker is None:
        _price_tracker = PriceTracker()
    return _price_tracker
