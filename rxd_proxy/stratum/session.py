import base58
import os
import json
import logging
import asyncio
import math
import time

from aiorpcx import (
    RPCSession,
    JSONRPCConnection,
    JSONRPCv1,
    Request,
    handler_invocation,
    RPCError,
    JSONRPC,
)
from ..state.template import TemplateState
from ..utils.enc import bech32_decode
from ..consensus.merkle import fold_branch_index0
from ..consensus.header import build_header80_le
from ..utils.hashers import dsha256, sha512_256d, radiant_pow
from aiohttp import ClientSession
from ..consensus.targets import target_to_diff1
from . import vardiff as _vardiff_mod

logger = logging.getLogger(__name__)

# Hashrate tracking based on share submissions - initialized after class definition
hashrate_tracker: "HashrateTracker"


async def _log_share_stats_background(
    worker: str, timestamp: int, accepted: bool, difficulty: float
):
    """Background task for logging share statistics without blocking share responses"""
    try:
        from ..db.schema import update_share_stats

        await update_share_stats(
            worker=worker,
            timestamp=timestamp,
            accepted=accepted,
            difficulty=difficulty,
        )
    except ImportError:
        pass  # Database not enabled
    except Exception as e:
        logger.debug("Background share stats logging failed: %s", e)


async def _record_best_share_background(
    worker: str,
    chain: str,
    block_height: int,
    share_difficulty: float,
    target_difficulty: float,
    timestamp: int,
    miner_software: str | None = None,
):
    """Background task for recording potential best shares"""
    try:
        from ..db.schema import record_best_share

        # Debug logging for high difficulty shares
        if share_difficulty > 100:
            logger.info(
                f"BEST SHARE BACKGROUND - {chain}: diff={share_difficulty:.2f}, "
                f"target={target_difficulty:.2f}, ratio={share_difficulty/target_difficulty:.6f}"
            )

        await record_best_share(
            worker=worker,
            chain=chain,
            block_height=block_height,
            share_difficulty=share_difficulty,
            target_difficulty=target_difficulty,
            timestamp=timestamp,
            miner_software=miner_software,
        )
    except ImportError:
        logger.warning("Database import failed for best share recording")
    except Exception as e:
        logger.error(f"Error in best share background task: {e}")
        # Don't let best share tracking interfere with mining


class HashrateTracker:
    """Enhanced hashrate tracker with EMA smoothing & confidence metrics."""

    def __init__(self, window_seconds: int = 300, ema_half_life: int = 120):
        self.window_seconds = window_seconds
        self.ema_half_life = ema_half_life
        # worker -> list[(timestamp, difficulty, accepted)]
        self.worker_shares: dict[str, list[tuple[float, float, bool]]] = {}
        # worker -> (ema_hashrate_hs, last_update_ts)
        self.worker_ema: dict[str, tuple[float, float]] = {}

    def add_share(self, worker: str, difficulty: float, accepted: bool = True):
        import time

        now = time.time()
        shares = self.worker_shares.setdefault(worker, [])
        shares.append((now, difficulty, accepted))
        cutoff = now - self.window_seconds
        self.worker_shares[worker] = [s for s in shares if s[0] >= cutoff]
        inst = self._instant(worker, now)
        ema_val, last_ts = self.worker_ema.get(worker, (inst, now))
        dt = max(0.0, now - last_ts)
        alpha = (
            1 - math.exp(-dt / self.ema_half_life) if self.ema_half_life > 0 else 1.0
        )
        ema_val = alpha * inst + (1 - alpha) * ema_val
        # Safety clamp: if legacy EMA wildly exceeds current instantaneous (e.g., after logic change)
        # reduce it to avoid misleading multi-order-of-magnitude displays.
        if inst > 0 and ema_val > inst * 64:  # 64x threshold is generous
            ema_val = inst
        self.worker_ema[worker] = (ema_val, now)

    def _instant(self, worker: str, now: float | None = None) -> float:
        if worker not in self.worker_shares:
            return 0.0
        if now is None:
            import time

            now = time.time()
        cutoff = now - self.window_seconds
        accepted = [s for s in self.worker_shares[worker] if s[2] and s[0] >= cutoff]
        if not accepted:
            return 0.0
        oldest = min(ts for ts, *_ in accepted)
        span = now - max(cutoff, oldest)

        # For very short spans (especially with 1-2 shares), use a minimum reasonable window
        # This prevents unrealistic hashrate spikes after proxy restart or new miner connection
        # Assume minimum 10 second span to avoid division by near-zero
        MIN_SPAN = 10.0
        if span < MIN_SPAN:
            span = MIN_SPAN

        total_d = sum(diff for ts, diff, _ in accepted)
        return (total_d * (2**32)) / span if total_d > 0 else 0.0

    def _confidence(self, worker: str) -> tuple[int, float]:
        if worker not in self.worker_shares:
            return 0, 1.0
        accepted = [s for s in self.worker_shares[worker] if s[2]]
        n = len(accepted)
        if n == 0:
            return 0, 1.0
        return n, 1 / math.sqrt(n)

    def get_hashrate_display(self, worker: str) -> dict:
        if worker not in self.worker_shares:
            return {
                "value": 0.0,
                "unit": "H/s",
                "display": "0.00 H/s",
                "instant": 0.0,
                "ema": 0.0,
                "shares": 0,
                "rel_error": 1.0,
            }
        inst = self._instant(worker)
        ema_val, _ = self.worker_ema.get(worker, (inst, 0.0))
        n_shares, rel_err = self._confidence(worker)
        display_hs = ema_val if ema_val > 0 else inst
        if display_hs >= 1_000_000_000:
            value, unit = display_hs / 1_000_000_000, "GH/s"
        elif display_hs >= 1_000_000:
            value, unit = display_hs / 1_000_000, "MH/s"
        elif display_hs >= 1_000:
            value, unit = display_hs / 1_000, "KH/s"
        else:
            value, unit = display_hs, "H/s"
        return {
            "value": value,
            "unit": unit,
            "display": f"{value:.2f} {unit}",
            "instant": inst,
            "ema": ema_val,
            "shares": n_shares,
            "rel_error": rel_err,
        }

    def get_hashrate_mhs(self, worker: str) -> float:
        result = self.get_hashrate_display(worker)
        unit = result["unit"]
        v = result["value"]
        if unit == "MH/s":
            return v
        if unit == "KH/s":
            return v / 1_000
        if unit == "H/s":
            return v / 1_000_000
        if unit == "GH/s":
            return v * 1_000
        return 0.0

    def get_interval_data(self, worker: str) -> dict:
        """Get share interval metrics for a worker (works with or without VarDiff)"""
        if worker not in self.worker_shares:
            return {
                "avg_interval": None,
                "ema_interval": None,
                "blended_interval": None,
                "share_count": 0,
            }

        import time

        now = time.time()

        shares = self.worker_shares[worker]
        accepted = [s for s in shares if s[2]]  # Only accepted shares

        avg_interval = None
        ema_interval = None

        if len(accepted) >= 2:
            # Calculate average interval between accepted shares
            first_ts = accepted[0][0]
            last_ts = accepted[-1][0]
            span = last_ts - first_ts
            if span > 0:
                avg_interval = span / (len(accepted) - 1)

            # Calculate EMA of inter-share intervals
            intervals = []
            for i in range(1, len(accepted)):
                interval = accepted[i][0] - accepted[i - 1][0]
                intervals.append(interval)

            if intervals:
                ema_val = intervals[0]
                for interval in intervals[1:]:
                    # Apply EMA with half-life of 120 seconds
                    alpha = (
                        1 - math.exp(-1.0 / self.ema_half_life)
                        if self.ema_half_life > 0
                        else 1.0
                    )
                    ema_val = alpha * interval + (1 - alpha) * ema_val
                ema_interval = ema_val

        # Blend average and EMA if both available
        if avg_interval and ema_interval:
            blended = 0.5 * avg_interval + 0.5 * ema_interval
        else:
            blended = ema_interval or avg_interval

        return {
            "avg_interval": avg_interval,
            "ema_interval": ema_interval,
            "blended_interval": blended,
            "share_count": len(accepted),
        }

    def remove_worker(self, worker: str):
        """Remove worker from tracking"""
        self.worker_shares.pop(worker, None)


# Global hashrate tracker instance
hashrate_tracker = HashrateTracker()


class StratumSession(RPCSession):
    def __init__(
        self,
        state: TemplateState,
        testnet: bool,
        node_url: str,
        static_share_difficulty: float,
        notification_manager,
        transport,
    ):
        connection = JSONRPCConnection(JSONRPCv1)
        super().__init__(transport, connection=connection)
        import logging

        self._state = state
        self._testnet = testnet
        self._notification_manager = notification_manager

        # Validate and clamp static_share_difficulty
        # Min: 0.001 (very easy, for testing)
        # Max: 10000000.0 (10M, for ASIC farms)
        if static_share_difficulty < 0.001:
            self.logger = logging.getLogger("Stratum-Proxy")
            self.logger.warning(
                "static_share_difficulty %.6f is below minimum 0.001, clamping to 0.001",
                static_share_difficulty,
            )
            static_share_difficulty = 0.001
        elif static_share_difficulty > 10000000.0:
            self.logger = logging.getLogger("Stratum-Proxy")
            self.logger.warning(
                "static_share_difficulty %.2f exceeds maximum 10000000.0, clamping to 10000000.0",
                static_share_difficulty,
            )
            static_share_difficulty = 10000000.0

        self._static_share_difficulty = static_share_difficulty
        self._client_addr = transport._remote_address
        self._transport = transport
        self._node_url = node_url
        self._extranonce1 = None
        self.logger = logging.getLogger("Stratum-Proxy")
        self._keepalive_task = None  # Keepalive task reference
        self._last_activity = None  # Track last activity time

        self.handlers = {
            "mining.subscribe": self.handle_subscribe,
            "mining.authorize": self.handle_authorize,
            "mining.submit": self.handle_submit,
            "mining.configure": self.handle_configure,
            "eth_submitHashrate": self.handle_eth_submitHashrate,
        }

    async def handle_request(self, request):
        if isinstance(request, Request):
            handler = self.handlers.get(request.method, None)
            if not handler:
                return
        else:
            return

        # For mining.submit, filter out extra parameters like 'rigid' from mining pool software
        # The Stratum protocol spec defines these parameters, but some pool software adds extras
        if request.method == "mining.submit" and isinstance(request.args, dict):
            # Keep only the expected parameters for mining.submit
            # Standard Stratum: worker, job_id, extranonce2, ntime, nonce
            # Some pools send: login, pass, rigid, etc. - we filter these out
            expected_params = {"worker", "job_id", "extranonce2", "ntime", "nonce"}
            filtered_args = {
                k: v for k, v in request.args.items() if k in expected_params
            }
            # Reconstruct request with filtered parameters as a dict
            request = Request(request.method, filtered_args)

        return await handler_invocation(handler, request)()

    async def connection_lost(self):
        # Send disconnection notification
        worker = getattr(self, "_worker_name", None)
        if worker:
            miner_software = getattr(self, "_miner_software", None)
            await self._notification_manager.notify_miner_disconnected(
                worker=worker,
                miner_software=miner_software,
            )

            # Mark miner as disconnected in database
            try:
                from ..db.schema import mark_miner_disconnected

                await mark_miner_disconnected(worker)
            except ImportError:
                pass  # Database not enabled
            except Exception as e:
                self.logger.debug("Miner session disconnect marking failed: %s", e)

            # Log to database if enabled
            try:
                from ..db.schema import log_connection_event
                import time

                await log_connection_event(
                    worker=worker,
                    miner_software=miner_software or "Unknown",
                    event_type="disconnected",
                    timestamp=int(time.time()),
                )
            except ImportError:
                pass  # Database not enabled
            except Exception as e:
                self.logger.debug("Database logging failed: %s", e)

        # Cancel keepalive task
        if self._keepalive_task and not self._keepalive_task.done():
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass

        try:
            wid = getattr(self, "_worker_name", None)
            if wid:
                hashrate_tracker.remove_worker(wid)
        except Exception as e:
            self.logger.debug("Failed to remove worker from hashrate tracker: %s", e)

        self._state.new_sessions.discard(self)
        self._state.all_sessions.discard(self)

        # Reset payout address when all miners disconnect
        # This allows the next miner to connect to set their address
        if not self._state.all_sessions and not self._state.new_sessions:
            self.logger.info("All miners disconnected - resetting payout address")
            self._state.pub_h160 = None

        try:
            result = super().connection_lost()
            if asyncio.iscoroutine(result):
                await result
        except TypeError:
            try:
                super().connection_lost()  # type: ignore[misc]
            except Exception as e:
                self.logger.debug("Error calling connection_lost: %s", e)

    async def handle_subscribe(self, *args):
        if self not in self._state.all_sessions:
            self._state.new_sessions.add(self)
        self._state.bits_counter += 1
        subscription_id = f"subscription_{self._state.bits_counter}"
        self._extranonce1 = self._state.bits_counter.to_bytes(4, "big").hex()
        extranonce2_size = 4

        # Capture miner software name/version from first parameter
        if args and len(args) > 0 and args[0]:
            self._miner_software = args[0]
            self.logger.info("New miner connection: %s", self._miner_software)
        else:
            self._miner_software = "Unknown"

        return [
            [
                ["mining.set_difficulty", subscription_id],
                ["mining.notify", subscription_id],
            ],
            self._extranonce1,
            extranonce2_size,
        ]

    async def handle_authorize(self, username: str, password: str):
        self._worker_id = username
        self._worker_name = username  # Store for disconnection notification
        address = username.split(".")[0]
        pub_h160 = None
        try:
            # Radiant uses legacy P2PKH addresses starting with 1 (mainnet) or m/n (testnet)
            # Decode base58check address
            addr_decoded = base58.b58decode_check(address)
            
            # Radiant mainnet P2PKH version byte is 0x00 (same as Bitcoin)
            # Radiant testnet P2PKH version byte is 0x6F (111 decimal)
            if self._testnet:
                expected_versions = [111, 196]  # Testnet P2PKH (m/n) and P2SH
            else:
                expected_versions = [0, 5]  # Mainnet P2PKH (1) and P2SH (3)
            
            if addr_decoded[0] not in expected_versions:
                if self._testnet:
                    raise RPCError(20, f"Invalid testnet address version for {address}")
                else:
                    raise RPCError(20, f"Invalid mainnet address version for {address}")
            
            pub_h160 = addr_decoded[1:]
            if len(pub_h160) != 20:
                raise RPCError(20, f"Invalid address hash length: {address}")
                
        except RPCError:
            raise
        except Exception as e:
            raise RPCError(20, f"Address validation failed: {address} - {str(e)}")
        
        if not self._state.pub_h160:
            self._state.pub_h160 = pub_h160

        # Register this session now
        self._state.all_sessions.add(self)
        self._state.new_sessions.discard(self)

        # Store connection time for uptime tracking
        import time

        self._connection_time = time.time()

        # Send connection notification
        miner_software = getattr(self, "_miner_software", None)
        await self._notification_manager.notify_miner_connected(
            worker=username,
            miner_software=miner_software,
        )

        # Record miner session in database
        try:
            from ..db.schema import record_miner_session

            await record_miner_session(
                worker_name=username,
                miner_software=miner_software or "Unknown",
            )
        except ImportError:
            pass  # Database not enabled
        except Exception as e:
            self.logger.debug("Miner session recording failed: %s", e)

        # Log to database if enabled
        try:
            from ..db.schema import log_connection_event
            import time

            await log_connection_event(
                worker=username,
                miner_software=miner_software or "Unknown",
                event_type="connected",
                timestamp=int(time.time()),
            )
        except ImportError:
            pass  # Database not enabled
        except Exception as e:
            self.logger.debug("Database logging failed: %s", e)

        # Start keepalive task
        if not self._keepalive_task or self._keepalive_task.done():
            loop = asyncio.get_event_loop()
            self._last_activity = loop.time()
            self._keepalive_task = asyncio.create_task(self._keepalive_loop())
            self.logger.debug("Started keepalive task for %s", username)

        # If a job exists, send it right away
        job = self._state.current_job_params()
        if job:
            if _vardiff_mod.vardiff_manager is not None:
                try:
                    difficulty = await _vardiff_mod.vardiff_manager.get_difficulty(
                        self._worker_id
                    )
                except Exception:
                    difficulty = self._static_share_difficulty
            else:
                difficulty = self._static_share_difficulty
            self._share_difficulty = difficulty
            await self.send_notification("mining.set_difficulty", (difficulty,))
            await self.send_notification("mining.notify", job)
            self._last_activity = (
                asyncio.get_event_loop().time()
            )  # Reset activity timer
            return True

    async def handle_configure(self, extensions):
        return {}

    async def _keepalive_loop(self):
        """Send periodic keepalive messages to prevent miner disconnection"""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds

                # If no activity for 45 seconds, send a notification
                loop = asyncio.get_event_loop()
                if self._last_activity and (loop.time() - self._last_activity > 45):
                    # Send a difficulty notification (same value, just to keep connection alive)
                    difficulty = getattr(self, "_share_difficulty", 1.0)
                    # If vardiff enabled, optionally refresh difficulty when sending keepalive
                    if _vardiff_mod.vardiff_manager is not None and getattr(
                        self, "_worker_id", None
                    ):
                        try:
                            vd = await _vardiff_mod.vardiff_manager.get_difficulty(
                                self._worker_id
                            )
                            if abs(vd - difficulty) / max(difficulty, 1e-9) >= 0.05:
                                difficulty = vd
                                self._share_difficulty = vd
                        except Exception as e:
                            self.logger.debug("Vardiff adjustment failed: %s", e)
                    await self.send_notification("mining.set_difficulty", (difficulty,))
                    self._last_activity = loop.time()
                    self.logger.debug(
                        "Sent keepalive to %s",
                        getattr(self, "_worker_id", "unknown"),
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Keepalive error: %s", e)
                break

    async def handle_submit(self, *args, **kwargs):
        """
        Handle mining.submit requests with flexible parameter handling.
        Some mining pool software sends extra parameters like 'rigid', 'login', 'pass'.

        Standard Stratum parameters:
        - worker (or login): Worker identifier
        - job_id: Job ID from the template
        - extranonce2 (or extranonce2_hex): Extranonce2 hex string
        - ntime (or ntime_hex): Block time hex string
        - nonce (or nonce_hex): Nonce hex string
        """
        # Parse parameters flexibly to handle different mining software
        worker = None
        job_id = None
        extranonce2_hex = None
        ntime_hex = None
        nonce_hex = None

        # Try to get from kwargs first (named parameters)
        worker = kwargs.get("worker") or kwargs.get("login")
        job_id = kwargs.get("job_id")
        extranonce2_hex = kwargs.get("extranonce2_hex") or kwargs.get("extranonce2")
        ntime_hex = kwargs.get("ntime_hex") or kwargs.get("ntime")
        nonce_hex = kwargs.get("nonce_hex") or kwargs.get("nonce")

        # Fall back to positional arguments if not found in kwargs
        if len(args) >= 1 and not worker:
            worker = args[0]
        if len(args) >= 2 and not job_id:
            job_id = args[1]
        if len(args) >= 3 and not extranonce2_hex:
            extranonce2_hex = args[2]
        if len(args) >= 4 and not ntime_hex:
            ntime_hex = args[3]
        if len(args) >= 5 and not nonce_hex:
            nonce_hex = args[4]

        # Validate we have all required parameters
        if not all([worker, job_id, extranonce2_hex, ntime_hex, nonce_hex]):
            raise RPCError(
                -32602, "Invalid request arguments - missing required parameters"
            )

        # Type narrowing for Pylance - these are guaranteed non-None after the check above
        assert worker is not None
        assert job_id is not None
        assert extranonce2_hex is not None
        assert ntime_hex is not None
        assert nonce_hex is not None

        # Reset activity timer on any submission
        loop = asyncio.get_event_loop()
        self._last_activity = loop.time()

        state = self._state

        # Snapshot state for consistent block building
        coinbase1_nowit_snapshot = state.coinbase1_nowit
        coinbase2_nowit_snapshot = state.coinbase2_nowit
        merkle_branches_snapshot = list(state.merkle_branches)
        version_snapshot = state.version
        prevHash_header_snapshot = state.prevHash_header  # LE bytes for header building
        bits_le_snapshot = state.bits_le

        if job_id != hex(state.job_counter)[2:]:
            self.logger.error("Miner submitted unknown/old job %s", job_id)
            return False

        if not (
            state.coinbase1
            and state.coinbase2
            and state.coinbase1_nowit
            and state.coinbase2_nowit
        ):
            self.logger.error("Coinbase parts not ready")
            return False

        # Additional state validation for header building
        if not (prevHash_header_snapshot and bits_le_snapshot and state.target):
            self.logger.error("Header state not ready")
            return False

        # Type narrowing for Pylance - snapshots are guaranteed non-None after checks
        assert coinbase1_nowit_snapshot is not None
        assert coinbase2_nowit_snapshot is not None

        en1 = bytes.fromhex(self._extranonce1 or "")
        en2 = bytes.fromhex(extranonce2_hex)

        coinbase_tx = state.coinbase1 + en1 + en2 + state.coinbase2
        coinbase_nowit = coinbase1_nowit_snapshot + en1 + en2 + coinbase2_nowit_snapshot
        coinbase_txid_le = dsha256(coinbase_nowit)

        merkle_root_le = fold_branch_index0(
            coinbase_txid_le, [bytes.fromhex(x) for x in merkle_branches_snapshot]
        )

        ntime_le = bytes.fromhex(ntime_hex)[::-1]
        nonce_le = bytes.fromhex(nonce_hex)[::-1]
        
        # Debug: Log header components
        self.logger.debug(f"Header build - version: {version_snapshot}, prevHash_header: {prevHash_header_snapshot.hex()}")
        self.logger.debug(f"Header build - merkle_root_le: {merkle_root_le.hex()}, ntime_le: {ntime_le.hex()}, bits_le: {bits_le_snapshot.hex()}, nonce_le: {nonce_le.hex()}")
        
        header80 = build_header80_le(
            version_snapshot,
            prevHash_header_snapshot,  # Use LE bytes for header (not word-swapped)
            merkle_root_le,
            ntime_le,
            bits_le_snapshot,
            nonce_le,
        )

        self.logger.debug(f"Header80 ({len(header80)} bytes): {header80.hex()}")

        block_hash = dsha256(header80)[::-1]

        # Calculate SHA512/256d PoW hash for Radiant
        pow_digest_le = radiant_pow(header80)
        self.logger.debug(f"POW hash (LE): {pow_digest_le.hex()}")
        hnum = int.from_bytes(pow_digest_le, "little")
        self.logger.debug(f"Hash as int: {hnum}")

        # Check RXD target
        target_int = int(state.target, 16)
        is_block = hnum <= target_int

        # Difficulty we assigned to the miner (expected work per share)
        sent_diff = getattr(self, "_share_difficulty", 1.0) or 1.0
        DIFF1 = int(
            "00000000ffff0000000000000000000000000000000000000000000000000000", 16
        )
        share_diff = DIFF1 / max(1, hnum)

        # Accept share if it meets the target or the miner difficulty
        if not is_block and (share_diff / sent_diff) < 0.99:
            # Share is rejected due to insufficient difficulty
            self.logger.info(
                "Share rejected: insufficient difficulty (%.8f < %.8f)",
                share_diff,
                sent_diff,
            )

            # Log rejected share asynchronously
            import time

            current_timestamp = int(time.time())
            asyncio.create_task(
                _log_share_stats_background(
                    worker=worker,
                    timestamp=current_timestamp,
                    accepted=False,
                    difficulty=share_diff,
                )
            )
            # Record rejected share (confidence accounting) using assigned diff
            try:
                hashrate_tracker.add_share(worker, sent_diff, accepted=False)
            except Exception as e:
                self.logger.debug("Failed to record rejected share: %s", e)

            # Add rejected share to feed for dashboard visibility
            try:
                from ..web.share_feed import get_share_feed_manager

                feed_manager = get_share_feed_manager()
                self.logger.debug("Adding rejected share to feed for worker %s", worker)
                rxd_difficulty = target_to_diff1(target_int)
                asyncio.create_task(
                    feed_manager.add_share(
                        worker=worker,
                        share_difficulty=share_diff,
                        sent_difficulty=sent_diff,
                        is_block=False,
                        accepted=False,
                        rxd_difficulty=rxd_difficulty,
                        chain=None,
                        miner_software=getattr(self, "_miner_software", None),
                    )
                )
            except Exception as e:
                self.logger.error("Failed to add rejected share to feed: %s", e)

            return False

        block_msg = " (RXD BLOCK!)" if is_block else ""

        # Track share using the ASSIGNED difficulty to avoid conditional upward bias
        hashrate_tracker.add_share(worker, sent_diff, accepted=True)
        # Record accepted share for vardiff to adjust miner difficulty
        if _vardiff_mod.vardiff_manager is not None:
            try:
                await _vardiff_mod.vardiff_manager.record_share(
                    worker, share_difficulty=sent_diff
                )
                # Check if VarDiff updated difficulty and push to miner if changed
                new_diff = await _vardiff_mod.vardiff_manager.get_difficulty(worker)
                if abs(new_diff - sent_diff) / max(sent_diff, 1e-9) >= 0.05:
                    self._share_difficulty = new_diff
                    await self.send_notification("mining.set_difficulty", (new_diff,))
                    self.logger.debug("VarDiff adjusted difficulty for %s: %.4f -> %.4f", worker, sent_diff, new_diff)
            except Exception as e:
                self.logger.debug("Failed to record share for vardiff: %s", e)

        # Log share statistics asynchronously
        import time

        current_timestamp = int(time.time())

        asyncio.create_task(
            _log_share_stats_background(
                worker=worker,
                timestamp=current_timestamp,
                accepted=True,
                difficulty=share_diff,
            )
        )

        # Record regular shares (non-blocks) as potential best shares
        rxd_difficulty = target_to_diff1(target_int)
        if not is_block:
            asyncio.create_task(
                _record_best_share_background(
                    worker=worker,
                    chain="RXD",
                    block_height=state.height,
                    share_difficulty=share_diff,
                    target_difficulty=rxd_difficulty,
                    timestamp=current_timestamp,
                    miner_software=getattr(self, "_miner_software", None),
                )
            )

        # Always log accepted shares at INFO level
        self.logger.info(
            "Share accepted by %s - shareDiff=%.8f%s RXD diff: %.8f",
            worker,
            share_diff,
            block_msg,
            rxd_difficulty,
        )

        # Broadcast to share feed for real-time dashboard
        try:
            from ..web.share_feed import get_share_feed_manager

            feed_manager = get_share_feed_manager()
            asyncio.create_task(
                feed_manager.add_share(
                    worker=worker,
                    share_difficulty=share_diff,
                    sent_difficulty=sent_diff,
                    is_block=is_block,
                    accepted=True,
                    rxd_difficulty=rxd_difficulty,
                    chain="RXD" if is_block else None,
                    miner_software=getattr(self, "_miner_software", None),
                )
            )
        except Exception as e:
            self.logger.debug("Failed to add share to feed: %s", e)

        # Submit to Radiant blockchain
        if is_block:
            import time

            submit_time = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

            # Track submission result
            block_accepted = False
            block_height_for_notif = None

            async with ClientSession() as http:
                # Build block for submission
                tx_count = len(state.externalTxs) + 1
                if tx_count < 0xFD:
                    tx_count_hex = tx_count.to_bytes(1, "little").hex()
                elif tx_count <= 0xFFFF:
                    tx_count_hex = "fd" + tx_count.to_bytes(2, "little").hex()
                elif tx_count <= 0xFFFFFFFF:
                    tx_count_hex = "fe" + tx_count.to_bytes(4, "little").hex()
                else:
                    tx_count_hex = "ff" + tx_count.to_bytes(8, "little").hex()

                coinbase_full = (
                    state.coinbase1_nowit + en1 + en2 + state.coinbase2_nowit
                )

                block_hex = (
                    header80.hex()
                    + tx_count_hex
                    + coinbase_full.hex()
                    + "".join(state.externalTxs)
                )

                from ..rpc.rxd import submitblock

                state.logger.info("Submitting RXD block at height %d", state.height)
                state.logger.debug("RXD submit block: %s", block_hex[:200] + "...")

                js = await submitblock(http, self._node_url, block_hex)

                if not os.path.exists("./submit_history"):
                    os.mkdir("./submit_history")

                with open(
                    f"./submit_history/RXD_{state.height}_{state.job_counter}.txt",
                    "w",
                ) as f:
                    dump = f"=== RXD BLOCK SUBMISSION ===\n"
                    dump += f"Submission Time: {submit_time}\n"
                    dump += f"Worker: {worker}\n"
                    dump += f"Job ID: {job_id}\n"
                    dump += f"Block Height: {state.height}\n"
                    dump += f"Block Hash: {block_hash.hex()}\n"
                    dump += f"Extranonce1: {self._extranonce1}\n"
                    dump += f"Extranonce2: {extranonce2_hex}\n"
                    dump += f"Ntime: {ntime_hex}\n"
                    dump += f"Nonce: {nonce_hex}\n"
                    dump += f"Coinbase hex: {coinbase_full.hex()}\n"
                    dump += f"PoW Hash (SHA512/256d): {pow_digest_le.hex()}\n"
                    dump += f"Hash Number: {hnum}\n"
                    dump += f"Target: {target_int:064x}\n"
                    dump += f"Share Difficulty: {share_diff:.18f}\n"
                    dump += f"Header: {header80.hex()}\n"
                    dump += f"Block Hex Length: {len(block_hex)} chars\n"
                    dump += f"Transaction Count: {len(state.externalTxs) + 1}\n\n"
                    dump += f"RPC Response:\n{json.dumps(js, indent=2)}\n\n"
                    dump += f"Full State:\n{state.__repr__()}\n\n"
                    dump += f"Block Hex:\n{block_hex}"
                    f.write(dump)

                if js.get("error"):
                    self.logger.error("RXD submit error: %s", js["error"])
                else:
                    result = js.get("result")
                    self.logger.info("RXD submit result: %s", result)

                    # submitblock returns null on success
                    if result is None or result == "":
                        block_accepted = True
                        block_height_for_notif = state.height
                        assert block_height_for_notif is not None  # Type narrowing

                        # Record as best share since block was accepted
                        asyncio.create_task(
                            _record_best_share_background(
                                worker=worker,
                                chain="RXD",
                                block_height=state.height,
                                share_difficulty=share_diff,
                                target_difficulty=rxd_difficulty,
                                timestamp=current_timestamp,
                                miner_software=getattr(
                                    self, "_miner_software", None
                                ),
                            )
                        )

                # Send notifications after submission
                if block_accepted and block_height_for_notif is not None:
                    await self._notification_manager.notify_block_found(
                        chain="RXD",
                        height=block_height_for_notif,
                        block_hash=block_hash.hex(),
                        worker=worker,
                        difficulty=share_diff,
                        miner_software=getattr(self, "_miner_software", None),
                    )

                    # Log to database if enabled
                    try:
                        from ..db.schema import log_block_found
                        import time

                        await log_block_found(
                            chain="RXD",
                            height=block_height_for_notif,
                            block_hash=block_hash.hex(),
                            worker=worker,
                            miner_software=getattr(self, "_miner_software", None)
                            or "Unknown",
                            difficulty=share_diff,
                            timestamp=int(time.time()),
                            accepted=True,
                        )
                    except ImportError:
                        pass  # Database not enabled
                    except Exception as e:
                        self.logger.debug("Database logging failed: %s", e)

                    # Also log to in-memory tracker as fallback
                    try:
                        import time

                        from ..web.block_tracker import get_block_tracker

                        tracker = get_block_tracker()
                        tracker.add_block(
                            chain="RXD",
                            height=block_height_for_notif,
                            block_hash=block_hash.hex(),
                            worker=worker,
                            timestamp=int(time.time()),
                            accepted=True,
                            difficulty=share_diff,
                        )
                    except Exception as e:
                        self.logger.debug("In-memory block tracking failed: %s", e)

                    # Record RXD block for confirmation tracking if DB enabled
                    try:
                        from ..db.schema import record_block_for_confirmation

                        await record_block_for_confirmation(
                            chain="RXD",
                            height=block_height_for_notif,
                            block_hash=block_hash.hex(),
                            worker=worker,
                        )
                    except ImportError:
                        pass  # Database not enabled
                    except Exception as e:
                        self.logger.debug("Block confirmation tracking failed: %s", e)

        return True

    async def handle_eth_submitHashrate(self, hashrate: str, clientid: str):
        """Handle ETH-style hashrate reporting"""
        try:
            rate = int(hashrate, 16)
            worker = getattr(self, "_worker_id", "unknown")

            # Format hashrate with appropriate units
            if rate >= 1_000_000_000:
                rate_display = f"{rate / 1_000_000_000:.2f} GH/s"
            elif rate >= 1_000_000:
                rate_display = f"{rate / 1_000_000:.2f} MH/s"
            elif rate >= 1_000:
                rate_display = f"{rate / 1_000:.2f} KH/s"
            else:
                rate_display = f"{rate:.2f} H/s"

            self.logger.info(
                "ETH hashrate reported by %s: %s (note: using share-based calculation)",
                worker,
                rate_display,
            )
        except Exception as e:
            self.logger.debug("ETH hashrate parsing error: %s", e)
        return True
