#!/usr/bin/env python3
"""
Mempool keeper + wallet sweeper for Radiant node.

IceRiver RX0 miners silently stall on empty block templates (zero txs =
empty merkle_branch in mining.notify). This service watches the node
mempool and, when it is empty, sends a small transaction so the next
block template contains at least one real transaction.

Sends are triggered by mempool state, not a timer — when the network's
organic mempool has transactions, nothing is sent and nothing is spent.

It also sweeps the node wallet: keeps KEEP_BALANCE RXD on the node
(enough to fund keeper txs) and transfers the excess to COLD_ADDRESS.

Block rewards paid to the node wallet are coinbase outputs — they need
100 confirmations to mature, then get swept on the next check.
"""

import json
import logging
import os
import sys
import time
import urllib.request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s MempoolKeeper %(levelname)s %(message)s",
)
log = logging.getLogger("mempool-keeper")

RPC_HOST = os.environ.get("RXD_RPC_HOST", "radiant")
RPC_PORT = int(os.environ.get("RXD_RPC_PORT", "7332"))
RPC_USER = os.environ.get("RXD_RPC_USER", "")
RPC_PASS = os.environ.get("RXD_RPC_PASS", "")

# Keeper self-send: destination + size
TARGET_ADDRESS = os.environ.get("TARGET_ADDRESS", "")
SEND_AMOUNT = float(os.environ.get("SEND_AMOUNT", "0.001"))      # RXD per keeper tx
FEE_RXD = float(os.environ.get("FEE_RXD", "0.025"))               # ~226B tx @ 0.1 RXD/kB min
CHECK_INTERVAL = float(os.environ.get("CHECK_INTERVAL", "60"))    # seconds between checks
MIN_MEMPOOL_TXS = int(os.environ.get("MIN_MEMPOOL_TXS", "1"))     # send when size < this

# Sweeper: keep a float on the node, send the rest to cold storage
COLD_ADDRESS = os.environ.get("COLD_ADDRESS", "")
KEEP_BALANCE = float(os.environ.get("KEEP_BALANCE", "50"))        # RXD to leave on node
SWEEP_MIN = float(os.environ.get("SWEEP_MIN", "1"))               # sweep when excess > this
# Wallet fee rate for sendtoaddress (sweeps), RXD/kB. Post-upgrade min is
# 0.1 RXD/kB — wallet default is 100x lower and would produce stuck txs.
WALLET_FEE_RATE = float(os.environ.get("WALLET_FEE_RATE", "0.12"))

LOW_BALANCE_WARN = float(os.environ.get("LOW_BALANCE_WARN", "1.0"))

RPC_URL = f"http://{RPC_HOST}:{RPC_PORT}"
_req_id = 0


def rpc(method: str, params: list = None):
    global _req_id
    _req_id += 1
    body = json.dumps(
        {"jsonrpc": "1.0", "id": _req_id, "method": method, "params": params or []}
    ).encode()
    req = urllib.request.Request(RPC_URL, data=body)
    req.add_header("Content-Type", "application/json")
    import base64

    req.add_header(
        "Authorization",
        "Basic " + base64.b64encode(f"{RPC_USER}:{RPC_PASS}".encode()).decode(),
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        out = json.loads(resp.read())
    if out.get("error"):
        raise RuntimeError(f"{method}: {out['error']}")
    return out["result"]


def mempool_size() -> int:
    return int(rpc("getmempoolinfo")["size"])


def synced() -> bool:
    try:
        return rpc("getblockchaininfo")["verificationprogress"] > 0.9999
    except Exception:
        return False


def send_self_tx() -> str:
    """Build, sign and broadcast a small tx to TARGET_ADDRESS. Returns txid."""
    # Pick a spendable UTXO (unconfirmed change allowed so change chains work)
    needed = SEND_AMOUNT + FEE_RXD
    utxos = rpc("listunspent", [0, 9999999, [], True])
    utxo = None
    for u in sorted(utxos, key=lambda x: -x["amount"]):
        if u["amount"] >= needed and u.get("spendable", True):
            utxo = u
            break
    if not utxo:
        raise RuntimeError(
            f"No spendable UTXO >= {needed} RXD — fund the node wallet "
            "(radiant-cli getnewaddress, then send RXD to it)"
        )

    change_addr = rpc("getrawchangeaddress")
    change_amt = round(utxo["amount"] - needed, 8)

    outputs = [{TARGET_ADDRESS: SEND_AMOUNT}]
    if change_amt > 0.00000001:
        outputs.append({change_addr: change_amt})

    raw = rpc(
        "createrawtransaction",
        [[{"txid": utxo["txid"], "vout": utxo["vout"]}], *outputs],
    )
    signed = rpc("signrawtransactionwithwallet", [raw])
    if not signed.get("complete"):
        raise RuntimeError(f"Signing incomplete: {signed.get('errors')}")
    return rpc("sendrawtransaction", [signed["hex"]])


def sweep_to_cold() -> None:
    """Send balance above KEEP_BALANCE to COLD_ADDRESS (fee subtracted)."""
    if not COLD_ADDRESS:
        return
    bal = rpc("getwalletinfo")["balance"]  # confirmed spendable only
    excess = bal - KEEP_BALANCE
    if excess < SWEEP_MIN:
        return
    amount = round(excess, 8)
    # subtractfeefromamount=True so we send exactly `amount`, fee comes out of it
    txid = rpc("sendtoaddress", [COLD_ADDRESS, amount, "", "", True])
    log.info("Swept %.8f RXD to cold storage %s (txid %s)", amount, COLD_ADDRESS, txid)


def main() -> int:
    if not TARGET_ADDRESS:
        log.error("TARGET_ADDRESS not set — refusing to start")
        return 1

    log.info(
        "Starting: target=%s send=%s RXD fee=%s RXD interval=%ss min_mempool=%d",
        TARGET_ADDRESS, SEND_AMOUNT, FEE_RXD, CHECK_INTERVAL, MIN_MEMPOOL_TXS,
    )
    if COLD_ADDRESS:
        log.info(
            "Sweeper enabled: keep %.2f RXD on node, sweep excess>%s to %s",
            KEEP_BALANCE, SWEEP_MIN, COLD_ADDRESS,
        )
    else:
        log.info("Sweeper disabled (COLD_ADDRESS not set)")

    # Wallet default fee (1000 sat/kB) is far below the 0.1 RXD/kB post-upgrade
    # floor — pin it so sendtoaddress sweeps aren't rejected by the mempool.
    for _ in range(30):
        try:
            rpc("settxfee", [WALLET_FEE_RATE])
            log.info("Wallet fee rate set to %.4f RXD/kB", WALLET_FEE_RATE)
            break
        except Exception as e:
            log.warning("settxfee failed (%s) — retrying", e)
            time.sleep(10)

    while True:
        try:
            if not synced():
                log.debug("Node still syncing — skipping check")
            else:
                try:
                    sweep_to_cold()
                except Exception as e:
                    log.error("Sweep failed: %s", e)

                size = mempool_size()
                if size < MIN_MEMPOOL_TXS:
                    try:
                        bal = rpc("getwalletinfo")["balance"]
                        if bal < LOW_BALANCE_WARN:
                            log.warning("Wallet balance low: %.8f RXD — fund it soon", bal)
                        txid = send_self_tx()
                        log.info("Mempool empty — sent tx %s (fee %.4f RXD)", txid, FEE_RXD)
                    except Exception as e:
                        log.error("Send failed: %s", e)
        except Exception as e:
            log.warning("Node check failed: %s", e)

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    sys.exit(main())
