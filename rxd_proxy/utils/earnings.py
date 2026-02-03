"""Mining earnings and revenue calculations for Radiant (RXD)"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("EarningsCalc")

# Default block reward (in coins) - will be overridden by daemon values
# Radiant started at 50,000 RXD per block, halving every 2 years
RXD_BLOCK_REWARD = 25000.0  # Current reward after first halving


class EarningsCalculator:
    """Calculate mining earnings and expected revenue for Radiant"""

    @staticmethod
    def calculate_expected_blocks_per_day(
        hashrate_hs: float, network_difficulty: float
    ) -> float:
        """
        Calculate expected blocks per day.

        The formula is based on:
        - Average time between blocks = (difficulty * 2^32) / hashrate_hs
        - Blocks per second = hashrate_hs / (difficulty * 2^32)
        - Blocks per day = (blocks per second) * 86400

        Args:
            hashrate_hs: Your hashrate in H/s
            network_difficulty: Current network difficulty

        Returns:
            Expected number of blocks per day (float)
        """
        if hashrate_hs <= 0 or network_difficulty <= 0:
            return 0.0

        # 2^32 = 4294967296
        TWO_POW_32 = 4294967296

        # Blocks per second = hashrate / (difficulty * 2^32)
        blocks_per_second = hashrate_hs / (network_difficulty * TWO_POW_32)

        # Blocks per day
        blocks_per_day = blocks_per_second * 86400

        return blocks_per_day

    @staticmethod
    def calculate_daily_earnings(
        hashrate_hs: float,
        rxd_difficulty: float,
        rxd_price_btc: Optional[float] = None,
        rxd_price_usd: Optional[float] = None,
        rxd_block_reward: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Calculate estimated daily earnings for Radiant mining.

        Args:
            hashrate_hs: Your total hashrate in H/s
            rxd_difficulty: Current RXD network difficulty
            rxd_price_btc: RXD price in BTC (optional)
            rxd_price_usd: RXD price in USD (optional)
            rxd_block_reward: RXD block reward in coins (fetched from daemon)

        Returns:
            Dictionary with earnings estimates
        """
        # Use provided block reward or default
        rxd_reward = rxd_block_reward if rxd_block_reward else RXD_BLOCK_REWARD
        
        # Calculate expected blocks per day
        rxd_blocks_per_day = EarningsCalculator.calculate_expected_blocks_per_day(
            hashrate_hs, rxd_difficulty
        )

        # Total coins expected per day
        rxd_coins_per_day = rxd_blocks_per_day * rxd_reward

        result = {
            "hashrate_hs": hashrate_hs,
            "rxd_difficulty": rxd_difficulty,
            "rxd_block_reward": round(rxd_reward, 8),
            "rxd_blocks_per_day": round(rxd_blocks_per_day, 6),
            "rxd_coins_per_day": round(rxd_coins_per_day, 8),
        }

        # Add BTC/USD values if prices available
        if rxd_price_btc:
            rxd_btc_per_day = rxd_coins_per_day * rxd_price_btc
            result["rxd_btc_per_day"] = round(rxd_btc_per_day, 8)

        if rxd_price_usd:
            rxd_usd_per_day = rxd_coins_per_day * rxd_price_usd
            result["rxd_usd_per_day"] = round(rxd_usd_per_day, 2)

        # Calculate weekly/monthly estimates
        result["rxd_coins_per_week"] = round(rxd_coins_per_day * 7, 8)
        result["rxd_coins_per_month"] = round(rxd_coins_per_day * 30, 8)

        if rxd_price_usd:
            result["rxd_usd_per_week"] = round(rxd_coins_per_day * rxd_price_usd * 7, 2)
            result["rxd_usd_per_month"] = round(rxd_coins_per_day * rxd_price_usd * 30, 2)

        return result

    @staticmethod
    def format_earnings_display(earnings_data: Dict[str, Any]) -> str:
        """
        Format earnings data for display.

        Args:
            earnings_data: Dictionary from calculate_daily_earnings()

        Returns:
            Formatted string for display
        """
        lines = ["Mining: Radiant (RXD) - SHA512/256d"]
        lines.append(f"Hashrate: {earnings_data['hashrate_hs']:.2f} H/s")
        lines.append("")
        lines.append("Expected Daily Earnings:")
        lines.append(f"  RXD: {earnings_data['rxd_coins_per_day']:.8f} coins")
        
        if "rxd_usd_per_day" in earnings_data:
            lines.append(f"  Value: ${earnings_data['rxd_usd_per_day']:.2f} USD")

        return "\n".join(lines)
