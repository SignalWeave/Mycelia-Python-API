from __future__ import annotations

import json
import socket
import struct
import threading
import uuid
from typing import Callable
from typing import Optional
from typing import Union
from typing import cast

__all__ = [
    'Message',
    'Transformer',
    'Subscriber',
    'GlobalValues',
    'Globals',
    'OBJ_MESSAGE',
    'OBJ_TRANSFORMER',
    'OBJ_SUBSCRIBER',
    'CMD_SEND',
    'CMD_ADD',
    'CMD_REMOVE',
    'process_command',
    'get_local_ipv4',
    'MyceliaListener'
]

OBJ_MESSAGE = 1
OBJ_TRANSFORMER = 2
OBJ_SUBSCRIBER = 3
OBJ_GLOBALS = 4

_CMD_UNKNOWN = 0
CMD_SEND = 1
CMD_ADD = 2
CMD_REMOVE = 3
CMD_UPDATE = 4

_ENCODING = 'utf-8'
API_PROTOCOL_VER = 1

_PAYLOAD_TYPE = Union[str, bytes, bytearray, memoryview]


# --------Command Types--------------------------------------------------------

class _MyceliaObj(object):
    """A MyceliaObj is the type of functionality the user wishes to invoke in
    the Mycelia instance, such as sending a message, adding a subscriber, or
    removing a transformer from a route + channel.

    The MyceliaObj represents the super command
    { MESSAGE, TRANSFORM, SUBSCRIBE }, and it contains a command attr for the
    sub command { SEND, ADD, REMOVE }.
    """

    def __init__(self, obj_type: int) -> None:
        self.protocol_version: int = API_PROTOCOL_VER
        self.obj_type: int = obj_type
        self.cmd_type: int = _CMD_UNKNOWN
        self.uid: str = str(uuid.uuid4())


class Message(_MyceliaObj):
    def __init__(self, route: str, payload: _PAYLOAD_TYPE) -> None:
        """
        Args:
            route (str): Which route the Message will travel through.
            payload (Union[str, bytes, bytearray, memoryview]): The data to
             send to the broker.
        """
        super().__init__(OBJ_MESSAGE)
        self.route = route
        self.cmd_type = CMD_SEND
        self.payload = payload


class Transformer(_MyceliaObj):
    def __init__(self, route: str, channel: str, address: str) -> None:
        """
        Args:
            route (str): Which route the Message will travel through.
            channel (str): which channel to add the transformer to.
            address (str): Where the channel should forward the data to.
        """
        super().__init__(OBJ_TRANSFORMER)
        self.route = route
        self.cmd_type = CMD_ADD
        self.channel = channel
        self.address = address


class Subscriber(_MyceliaObj):
    def __init__(self, route: str, channel: str, address: str) -> None:
        """
        Args:
            route (str): Which route the Message will travel through.
            channel (str): which channel to add the subscriber to.
            address (str): Where the channel should forward the data to.
        """
        super().__init__(OBJ_SUBSCRIBER)
        self.route = route
        self.cmd_type = CMD_ADD
        self.channel = channel
        self.address = address


class GlobalValues(object):
    """The data struct that the broker should update values from.
    Only change the values that you need.
    """
    address: str = ''
    port: int = -1
    verbosity: int = -1
    print_tree: bool = None
    transform_timeout: str = ''


class Globals(_MyceliaObj):
    def __init__(self, payload: GlobalValues) -> None:
        """
        Args:
            payload (GlobalValues): The struct object mycelia.GlobalValues that
             contains the updated values.
        """
        super().__init__(OBJ_GLOBALS)
        self.cmd_type = CMD_UPDATE

        data = {}
        if payload.address != '':
            data['address'] = payload.address
        if payload.port > 0:
            data['port'] = payload.port
        if payload.verbosity > -1:
            data['verbosity'] = payload.verbosity
        if type(payload.print_tree) is bool:
            data['print_tree'] = payload.print_tree
        if payload.transform_timeout != '':
            data['transform_timeout'] = payload.transform_timeout

        if not data:
            raise ValueError('No valid GlobalValues were added.')

        self.payload = json.dumps(data)


# --------Message Handling-----------------------------------------------------

def _u8(n: int) -> bytes:
    """Pack unsigned 8-bit int."""
    return struct.pack('>B', n & 0xFF)


def _u32(n: int) -> bytes:
    """Pack unsigned 32-bit int as big-endian."""
    return struct.pack('>I', n & 0xFFFFFFFF)


def _pstr(s: str) -> bytes:
    """Length-prefixed string: [u32 len][bytes]."""
    b = s.encode(_ENCODING)
    return _u32(len(b)) + b


def _pbytes(b: bytes) -> bytes:
    """Length-prefixed bytes: [u32 len][bytes]."""
    bb = bytes(b)
    return _u32(len(bb)) + bb


def _resolve_cmd_type(obj: '_MyceliaObj') -> int:
    """Return effective command type, using defaults if unknown."""
    if getattr(obj, 'cmd_type', _CMD_UNKNOWN) != _CMD_UNKNOWN:
        return obj.cmd_type
    if obj.obj_type == OBJ_MESSAGE:
        return CMD_SEND
    if obj.obj_type == OBJ_GLOBALS:
        return CMD_UPDATE
    if obj.obj_type in (OBJ_SUBSCRIBER, OBJ_TRANSFORMER):
        return CMD_ADD
    raise ValueError(f'unknown cmd_type')


def _encode_mycelia_obj(obj: _MyceliaObj) -> bytes:
    """Encode a _MyceliaObj into protocol bytes.

    Layout (big-endian):
      [u32 proto_ver]
      [u32 obj_type]
      [u32 obj_cmd]
      [u32 len][uid bytes]
      [u32 len][route bytes]
      then one of:
        - if obj_type == OBJ_MESSAGE:
            [u32 len][payload bytes]
        - if obj_type in { OBJ_SUBSCRIBER, OBJ_TRANSFORMER }:
            [u32 len][channel bytes]
            [u32 len][address bytes]

    Args:
        obj: Any _MyceliaObj (Message, Subscriber, Transformer).
    Returns:
        Encoded byte sequence.
    Raises:
        ValueError: If obj has an unknown obj_type or missing required fields.
        TypeError: If payload type is unsupported.
    """
    # -----Header-----
    proto_ver = int(getattr(obj, 'protocol_version', API_PROTOCOL_VER))
    obj_type = int(obj.obj_type)
    cmd_type = _resolve_cmd_type(obj)
    uid = cast(str, obj.uid)

    out = bytearray()
    out += _u8(proto_ver)
    out += _u8(obj_type)
    out += _u8(cmd_type)

    # -----Sub-Header-----
    out += _pstr(uid)

    if obj_type in (OBJ_MESSAGE, OBJ_SUBSCRIBER, OBJ_TRANSFORMER):
        route = cast(str, getattr(obj, 'route'))
        out += _pstr(route)

    # -----Body-----
    if obj_type in (OBJ_MESSAGE, OBJ_GLOBALS):
        payload = getattr(obj, 'payload', b'')
        if isinstance(payload, str):
            payload = payload.encode(_ENCODING)
        elif not isinstance(payload, (bytes, bytearray, memoryview)):
            raise TypeError('payload must be str or bytes-like')
        out += _pbytes(payload)
    elif obj_type in (OBJ_SUBSCRIBER, OBJ_TRANSFORMER):
        channel = cast(str, getattr(obj, 'channel'))
        address = cast(str, getattr(obj, 'address'))
        out += _pstr(channel)
        out += _pstr(address)
    else:
        raise ValueError(f'unknown obj_type: {obj_type}')

    packet_bytes = bytes(out)
    packet = _u32(len(packet_bytes)) + packet_bytes

    return packet


def process_command(message: _MyceliaObj, address: str, port: int) -> None:
    """Sends the CommandType message."""
    frame = _encode_mycelia_obj(message)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((address, port))
        sock.sendall(frame)


# --------Network Boilerplate--------------------------------------------------

def get_local_ipv4() -> str:
    """Get the local machine's primary IPv4 address.
    If it cannot be determined, defaults to 127.0.0.1.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.connect(('10.255.255.255', 1))
            return sock.getsockname()[0]
        except Exception as e:
            print(f'Exception getting IPv4, defaulting to 127.0.0.1 - {e}')
            return '127.0.0.1'


_LOCAL_IPv4 = get_local_ipv4()


class MyceliaListener(object):
    """A listener object that binds to a socket and listens for messages.

    Has various utility for passing the message to a hosted processor.

    Example usage:
        >>> listener = MyceliaListener(message_processor=print)
        >>>
        >>> # In a GUI or signal handler or thread:
        >>> def external_shutdown():
        >>>     listener.stop()
        >>>
        >>> listener.start()
    """

    def __init__(self,
                 message_processor: Callable[[bytes], Optional[bytes]],
                 local_addr: str = _LOCAL_IPv4,
                 local_port: int = 5500) -> None:
        """
        Args:
            message_processor (Callable[[bytes], None]: Which function/object
             to send the byte payload to.

            local_addr (str): The address to bind the socket to, defaults to
             '127.0.0.1'.

            local_port (int): Which port to listen on. Defaults to 5500.
         """
        self._local_addr = local_addr
        self._local_port = local_port
        self._message_processor = message_processor

        self._stop_event = threading.Event()
        self._server_sock: socket.socket | None = None

    def _listen(self, sock: socket.socket) -> None:
        """While loop logic for listening to the socket and passing incoming
        data to the processor.
        """
        while not self._stop_event.is_set():
            try:
                conn, addr = sock.accept()
            except socket.timeout:
                continue
            except OSError:
                raise OSError('Socket was closed')

            with conn:
                print(f'Connected by {addr}')
                while not self._stop_event.is_set():
                    try:
                        payload = conn.recv(1024)
                    except OSError:
                        raise OSError('Payload buffer overflow.')

                    if not payload:
                        break

                    result = self._message_processor(payload)
                    if result is not None:
                        conn.sendall(result)

    def start(self) -> None:
        """Blocking call that starts the socket listener loop."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
            self._server_sock = server_sock
            server_sock.setsockopt(
                socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
            )
            server_sock.settimeout(1.0)
            server_sock.bind((self._local_addr, self._local_port))
            server_sock.listen()

            print(f'Listening on {self._local_addr}:{self._local_port}')
            self._listen(server_sock)

    def stop(self) -> None:
        """Stops and shuts down the listener."""
        self._stop_event.set()
        if self._server_sock:
            try:
                self._server_sock.close()
            except OSError:
                pass
