"""
# Mycelia Message Encoding

All encoding helper functions for sending a message.
"""


import struct


_ENCODING = 'utf-8'


def write_u8(n: int) -> bytes:
    """Pack unsigned 8-bit int."""
    return struct.pack('>B', n & 0xFF)


def write_u16(n: int) -> bytes:
    """Pack unsigned 16-bit int."""
    return struct.pack('>H', n & 0xFFFF)


def write_u32(n: int) -> bytes:
    """Pack unsigned 32-bit int as big-endian."""
    return struct.pack('>I', n & 0xFFFFFFFF)


def write_str8(s: str) -> bytes:
    """Length-prefixed string: [u8 len][bytes]."""
    b = s.encode(_ENCODING)
    return write_u8(len(b)) + b


def write_str16(s: str) -> bytes:
    """Length-prefixed string: [u16 len][bytes]."""
    b = s.encode(_ENCODING)
    return write_u16(len(b)) + b


def write_str32(s: str) -> bytes:
    """Length-prefixed string: [u32 len][bytes]."""
    b = s.encode(_ENCODING)
    return write_u32(len(b)) + b


def write_bytes16(b: bytes) -> bytes:
    """Length-prefixed bytes: [u16 len][bytes]."""
    bb = bytes(b)
    return write_u16(len(bb)) + bb
