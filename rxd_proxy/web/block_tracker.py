"""In-memory block tracking for when database is disabled"""

from collections import deque
from typing import Dict, List, Any
import time
import threading


class InMemoryBlockTracker:
    """Tracks recent blocks in memory when database is not available"""

    def __init__(self, max_blocks: int = 100):
        """
        Initialize the block tracker.

        Args:
            max_blocks: Maximum number of blocks to keep
        """
        self.max_blocks = max_blocks
        self.blocks: deque = deque(maxlen=max_blocks)
        self.lock = threading.Lock()

    def add_block(
        self,
        chain: str,
        height: int,
        block_hash: str,
        worker: str,
        timestamp: int,
        accepted: bool = True,
        difficulty: float = 0.0,
    ) -> None:
        """
        Add a block to the in-memory tracker.

        Args:
            chain: Chain name (RXD)
            height: Block height
            block_hash: Block hash
            worker: Worker/miner name that found the block
            timestamp: Unix timestamp
            accepted: Whether block was accepted
            difficulty: Block difficulty
        """
        block_data = {
            "id": None,  # No database ID
            "chain": chain.upper(),
            "height": height,
            "hash": block_hash,
            "worker": worker,
            "timestamp": timestamp,
            "accepted": accepted,
            "difficulty": difficulty,
        }

        with self.lock:
            self.blocks.appendleft(block_data)

    def get_blocks_by_chain(
        self, chain: str, limit: int = 10, offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get recent blocks for a specific chain with pagination.

        Args:
            chain: Chain name (RXD)
            limit: Maximum number of blocks to return
            offset: Number of blocks to skip

        Returns:
            Dictionary with 'blocks' list and 'total' count, sorted newest first
        """
        with self.lock:
            # Filter blocks by chain
            blocks = [b for b in self.blocks if b["chain"].upper() == chain.upper()]

        total = len(blocks)
        return {"blocks": blocks[offset : offset + limit], "total": total}

    def get_all_blocks(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """
        Get all blocks with pagination.

        Args:
            limit: Maximum number of blocks to return
            offset: Number of blocks to skip

        Returns:
            Dictionary with 'blocks' list and 'total' count
        """
        with self.lock:
            all_blocks = list(self.blocks)

        # Already sorted by timestamp descending (newest first via appendleft)
        total = len(all_blocks)
        blocks = all_blocks[offset : offset + limit]

        return {"blocks": blocks, "total": total}

    def get_total_blocks(self) -> Dict[str, int]:
        """Get total block counts"""
        with self.lock:
            return {
                "RXD": len(self.blocks),
                "total": len(self.blocks),
            }

    def clear(self) -> None:
        """Clear all tracked blocks"""
        with self.lock:
            self.blocks.clear()


# Global instance
_block_tracker: InMemoryBlockTracker | None = None


def get_block_tracker() -> InMemoryBlockTracker:
    """Get or create the global block tracker instance"""
    global _block_tracker
    if _block_tracker is None:
        _block_tracker = InMemoryBlockTracker(max_blocks=100)
    return _block_tracker
