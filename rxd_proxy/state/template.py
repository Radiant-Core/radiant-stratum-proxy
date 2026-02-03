from dataclasses import dataclass, field
from typing import Optional, List, Set
from aiorpcx import RPCSession


@dataclass
class TemplateState:
    height: int = -1
    timestamp: int = -1
    pub_h160: Optional[bytes] = None
    bits: Optional[str] = None
    target: Optional[str] = None
    headerHash: Optional[str] = None
    version: int = -1
    prevHash_le: Optional[bytes] = None  # Word-swapped for stratum notifications
    prevHash_be: Optional[bytes] = None  # Original BE bytes
    prevHash_header: Optional[bytes] = None  # LE bytes for header building (simple reversal)
    externalTxs: List[str] = field(default_factory=list)
    coinbase_tx: Optional[bytes] = None
    coinbase_txid: Optional[bytes] = None
    coinbase1: Optional[bytes] = None
    coinbase2: Optional[bytes] = None
    merkle_branches: List[str] = field(default_factory=list)
    coinbase_branch: List[bytes] = field(default_factory=list)
    coinbase_index: int = 0
    current_commitment: Optional[str] = None
    new_sessions: Set[RPCSession] = field(default_factory=set)
    all_sessions: Set[RPCSession] = field(default_factory=set)
    awaiting_update: bool = False
    job_counter: int = 0
    bits_counter: int = 0
    header_prefix: Optional[bytes] = None
    bits_le: Optional[bytes] = None
    coinbase1_nowit: Optional[bytes] = None
    coinbase2_nowit: Optional[bytes] = None
    advertised_diff: Optional[float] = None

    def __post_init__(self):
        import logging

        self.logger = logging.getLogger("Stratum-Proxy")

    def current_job_params(self):
        if not (self.coinbase1_nowit and self.coinbase2_nowit and self.prevHash_le and self.bits):
            return None
        return [
            hex(self.job_counter)[2:],
            self.prevHash_le.hex(),
            self.coinbase1_nowit.hex(),
            self.coinbase2_nowit.hex(),
            self.merkle_branches,
            self.version.to_bytes(4, "big").hex(),
            self.bits,
            self.timestamp.to_bytes(4, "big").hex(),
            True,
        ]
