"""
# Mycelia Message Decoding

All decoding helper functions for sending a message.
"""


import socket


def recv_exact(sock: socket.socket, n: int) -> bytes:
    """Read exactly n bytes or raise socket.timeout / ConnectionError."""
    chunks = []
    remaining = n
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise ConnectionError('Socket closed while reading.')
        chunks.append(chunk)
        remaining -= len(chunk)
    return b''.join(chunks)
