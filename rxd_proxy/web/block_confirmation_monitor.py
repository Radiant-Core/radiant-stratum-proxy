"""
Block Confirmation Monitor - Periodic task for checking block confirmations and detecting orphans.
Runs every 5 minutes to poll blockchain for confirmation status.
"""

import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger("BlockConfirmationMonitor")

# Global monitor instance
_confirmation_monitor: Optional["BlockConfirmationMonitor"] = None


class BlockConfirmationMonitor:
    """
    Monitors block confirmations and detects orphaned blocks.
    Runs a background task that polls every 5 minutes.
    """

    def __init__(
        self,
        check_interval_seconds: int = 300,  # 5 minutes
    ):
        self.check_interval = check_interval_seconds
        self.task = None
        self.running = False
        self.node_url = None
        self.notification_manager = None
        self.seeding_complete = False  # Track if initial seeding is done

    def set_rpc_url(self, rxd_url: str):
        """Set RPC URL for Radiant node"""
        self.node_url = rxd_url

    def set_notification_manager(self, notification_manager):
        """Set notification manager for alerts"""
        self.notification_manager = notification_manager

    async def get_block_confirmations(self, block_hash: str) -> tuple[int, bool]:
        """
        Query Radiant blockchain for block confirmations.
        Returns: (confirmations, is_orphaned)
        """
        try:
            if not self.node_url:
                logger.warning("RXD RPC URL not configured")
                return (0, False)

            from aiohttp import ClientSession

            async with ClientSession() as session:
                from ..rpc.rxd import getblock

                try:
                    response = await getblock(session, self.node_url, block_hash)

                    # JSON-RPC response is wrapped in "result" field
                    if not response or "error" in response or response.get("error"):
                        logger.debug(f"RXD getblock error: {response}")
                        # If block not found, it's been orphaned
                        return (0, True)

                    # Extract the actual block data from the result field
                    result = response.get("result", {})
                    if not result:
                        logger.debug(f"RXD getblock returned empty result: {response}")
                        return (0, True)

                    # Block found - check confirmation count
                    confirmations = result.get("confirmations", 0)

                    # Block is orphaned if confirmations is 0 or negative
                    # (confirmations > 0 means it's in the main chain)
                    is_orphaned = confirmations <= 0

                    return (confirmations, is_orphaned)

                except Exception as e:
                    logger.error(f"RXD confirmation check failed: {e}")
                    return (0, False)

        except Exception as e:
            logger.error(f"RXD RPC error: {e}")
            return (0, False)

    async def check_confirmations_loop(self):
        """Main confirmation checking loop - runs every 5 minutes"""
        from ..db.schema import (
            get_pending_blocks,
            check_block_confirmations,
        )

        logger.info(
            f"Starting block confirmation monitor (checking every {self.check_interval}s)"
        )

        while self.running:
            try:
                # Get all pending blocks
                pending_rxd = await get_pending_blocks("RXD")

                if pending_rxd and self.node_url:
                    logger.info(
                        f"Checking confirmations for {len(pending_rxd)} RXD blocks"
                    )
                    await check_block_confirmations(
                        "RXD",
                        self.get_block_confirmations,
                        self.node_url,
                        self.notification_manager,
                        skip_notifications=not self.seeding_complete,
                    )

                # Wait for next check interval
                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in confirmation check loop: {e}")
                # Wait before retrying on error
                await asyncio.sleep(self.check_interval)

        logger.info("Block confirmation monitor stopped")

    async def start(self):
        """Start the confirmation monitoring background task"""
        if self.running:
            logger.warning("Confirmation monitor already running")
            return

        self.running = True
        self.task = asyncio.create_task(self.check_confirmations_loop())
        logger.info("Block confirmation monitor started")

    async def stop(self):
        """Stop the confirmation monitoring background task"""
        self.running = False
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Block confirmation monitor stopped")


def get_confirmation_monitor() -> BlockConfirmationMonitor:
    """Get or create global confirmation monitor instance"""
    global _confirmation_monitor
    if _confirmation_monitor is None:
        _confirmation_monitor = BlockConfirmationMonitor()
    return _confirmation_monitor


def set_confirmation_monitor(monitor: BlockConfirmationMonitor):
    """Set global confirmation monitor instance"""
    global _confirmation_monitor
    _confirmation_monitor = monitor
