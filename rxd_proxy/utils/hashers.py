import hashlib
from hashlib import sha256


def dsha256(b: bytes) -> bytes:
    """Double SHA256 hash."""
    return sha256(sha256(b).digest()).digest()


def sha512_256d(b: bytes) -> bytes:
    """
    Double SHA512/256 hash - Radiant's proof-of-work algorithm.
    SHA512/256 uses a DIFFERENT IV than regular SHA512 (not just truncation).
    This matches the sph_sha512_256_init() used in coinminerz-multi-hashing.
    """
    h1 = hashlib.new('sha512_256', b).digest()  # First round: proper SHA-512/256
    h2 = hashlib.new('sha512_256', h1).digest()  # Second round: proper SHA-512/256
    return h2


def radiant_pow(header80: bytes) -> bytes:
    """
    Radiant proof-of-work hash using SHA512/256d algorithm.
    """
    return sha512_256d(header80)
