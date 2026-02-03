from typing import List, Tuple
import logging
from ..utils.enc import var_int, op_push
from ..utils.hashers import dsha256

logger = logging.getLogger(__name__)


def encode_height_bip34(height: int) -> bytes:
    """
    Encode block height for BIP34 coinbase scriptSig.
    
    For heights 1-16, uses OP_1 through OP_16 opcodes.
    For height 0 or heights > 16, uses serialized script number format.
    
    This matches the Radiant node's ScriptInt::fromIntUnchecked behavior.
    """
    if height == 0:
        return bytes([0x00])  # OP_0
    elif 1 <= height <= 16:
        # OP_1 = 0x51, OP_2 = 0x52, ..., OP_16 = 0x60
        return bytes([0x50 + height])  # OP_N encoding
    else:
        # For heights > 16, use the serialized script number format
        # Serialize as little-endian, handling sign bit
        neg = height < 0
        absvalue = -height if neg else height
        result = bytearray()
        while absvalue:
            result.append(absvalue & 0xff)
            absvalue >>= 8
        # Handle sign bit
        if result[-1] & 0x80:
            result.append(0x80 if neg else 0)
        elif neg:
            result[-1] |= 0x80
        # Add push opcode for the length
        return op_push(len(result)) + bytes(result)


def build_coinbase(
    pub_h160: bytes,
    height: int,
    arbitrary: bytes,
    miner_value: int,
    outputs_extra: List[Tuple[int, bytes]],
):
    """
    Build a Radiant coinbase transaction.
    
    Radiant uses standard Bitcoin-style transactions (no SegWit).
    Transaction version is typically 1 or 2.
    """
    # Encode height for BIP34 (uses OP_N for small values 1-16)
    bip34_height = encode_height_bip34(height)
    
    logger.info(f"Building coinbase for height {height}, BIP34 encoded: {bip34_height.hex()}")

    # Build coinbase scriptSig: height encoding + arbitrary data
    # Note: bip34_height already includes the opcode/push prefix for heights 1-16
    coinbase_script_without_extranonces = (
        bip34_height + op_push(len(arbitrary)) + arbitrary
    )

    extranonce_placeholder_size = 8
    total_script_length = (
        len(coinbase_script_without_extranonces) + extranonce_placeholder_size
    )

    coinbase_txin_start = (
        bytes(32)
        + b"\xff" * 4
        + var_int(total_script_length)
        + coinbase_script_without_extranonces
    )
    coinbase_txin_end = b"\xff" * 4

    # Build miner output - P2PKH for Radiant addresses
    # P2PKH: OP_DUP OP_HASH160 <20-byte-hash> OP_EQUALVERIFY OP_CHECKSIG
    vout_to_miner = b"\x76\xa9\x14" + pub_h160 + b"\x88\xac"

    outputs = [
        miner_value.to_bytes(8, "little") + op_push(len(vout_to_miner)) + vout_to_miner
    ]

    # Add extra outputs (e.g., miner fund)
    for sat, script in outputs_extra:
        outputs.append(sat.to_bytes(8, "little") + op_push(len(script)) + script)

    num_outputs = len(outputs)
    coinbase_txin = coinbase_txin_start + coinbase_txin_end

    # Radiant uses version 1 or 2 for transactions (standard Bitcoin format)
    tx_version = 1
    
    # Full coinbase transaction (no witness data for Radiant)
    coinbase_tx = (
        tx_version.to_bytes(4, "little")
        + b"\x01"  # 1 input
        + coinbase_txin
        + var_int(num_outputs)
        + b"".join(outputs)
        + bytes(4)  # locktime
    )

    # Split for stratum protocol
    coinbase1 = tx_version.to_bytes(4, "little") + b"\x01" + coinbase_txin_start
    coinbase2 = (
        coinbase_txin_end + var_int(num_outputs) + b"".join(outputs) + bytes(4)
    )

    # For Radiant, coinbase1_nowit and coinbase2_nowit are the same as coinbase1 and coinbase2
    # since there's no witness data
    coinbase1_nowit = coinbase1
    coinbase2_nowit = coinbase2

    # Calculate txid using double SHA256
    coinbase_txid = dsha256(coinbase_tx)

    return (
        coinbase_tx,
        coinbase_txid,
        coinbase1,
        coinbase2,
        coinbase1_nowit,
        coinbase2_nowit,
    )
