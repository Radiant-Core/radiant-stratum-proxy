# Radiant blockchain PoW limits
# Note: Radiant uses SHA512/256d algorithm
POW_LIMIT = int(
    "00000000ffffffffffffffffffffffffffffffffffffffffffffffffffffffff", 16
)  # Radiant consensus powLimit

# Standard Bitcoin-style diff1 target for difficulty calculations
DIFF1_TARGET = int(
    "00000000ffff0000000000000000000000000000000000000000000000000000", 16
)


def bits_to_target(bits_hex: str) -> int:
    """Convert compact bits representation to full target value."""
    bits = int(bits_hex, 16)
    exp = bits >> 24
    mant = bits & 0xFFFFFF
    if exp <= 3:
        target_int = mant >> (8 * (3 - exp))
    else:
        target_int = mant << (8 * (exp - 3))
    return target_int


def normalize_be_hex(h: str) -> str:
    """Normalize a hex string to 64 characters (32 bytes), zero-padded."""
    return h.lower().zfill(64)


def target_to_diff1(target_int: int) -> float:
    """Convert a target value to difficulty (diff1-based)."""
    if target_int == 0:
        return float("inf")
    return DIFF1_TARGET / target_int
