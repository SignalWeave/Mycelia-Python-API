from __future__ import annotations

import json
import socket
import struct
import threading
import uuid
from typing import Callable
from typing import Optional
from typing import Union


__all__ = [
    'Message',
    'Transformer',
    'Subscriber',
    'GlobalValues',
    'Action',
    'Globals',
    'CMD_SEND',
    'CMD_ADD',
    'CMD_REMOVE',
    'CMD_SIGTERM',
    'send',
    'get_local_ipv4',
    'MyceliaListener'
]

OBJ_MESSAGE = 1
OBJ_TRANSFORMER = 2
OBJ_SUBSCRIBER = 3
OBJ_GLOBALS = 20
OBJ_ACTION = 50

_CMD_UNKNOWN = 0
CMD_SEND = 1
CMD_ADD = 2
CMD_REMOVE = 3
CMD_UPDATE = 20
CMD_SIGTERM = 50

_ENCODING = 'utf-8'
API_PROTOCOL_VER = 1

_PAYLOAD_TYPE = Union[str, bytes, bytearray, memoryview]


class MissingSecurityTokenError(Exception):
    """User has not provided a security token."""


# --------Command Types--------------------------------------------------------

class _MyceliaObj(object):
    """A MyceliaObj is the type of functionality the user wishes to invoke in
    the Mycelia instance, such as sending a message, adding a subscriber, or
    removing a transformer from a route + channel.

    The MyceliaObj represents the super command
    { MESSAGE, TRANSFORM, SUBSCRIBE, GLOBALS, ... }, and it contains a command
    attr for the sub command { SEND, ADD, REMOVE, UPDATE, ... }.
    """

    def __init__(self, obj_type: int) -> None:
        self.protocol_version: int = API_PROTOCOL_VER
        self.obj_type: int = obj_type
        self.cmd_type: int = _CMD_UNKNOWN
        self.return_address: str = ''
        self.arg1: str = ''
        self.arg2: str = ''
        self.arg3: str = ''
        self.arg4: str = ''
        self.payload: _PAYLOAD_TYPE = ''

    @property
    def cmd_valid(self) -> bool:
        raise NotImplementedError


class Message(_MyceliaObj):
    def __init__(self,
                 return_address: str,
                 route: str,
                 payload: _PAYLOAD_TYPE) -> None:
        """
        Args:
            return_address (str): Address the broker should respond to with
             updates.
            route (str): Which route the Message will travel through.
            payload (Union[str, bytes, bytearray, memoryview]): The data to
             send to the broker.
        """
        super().__init__(OBJ_MESSAGE)
        self.cmd_type = CMD_SEND
        self.return_address = return_address
        self.arg1 = route
        self.payload = payload

    @property
    def cmd_valid(self) -> bool:
        return self.cmd_type == CMD_SEND


class Transformer(_MyceliaObj):
    def __init__(self,
                 return_address: str,
                 route: str,
                 channel: str,
                 address: str) -> None:
        """
        Args:
            return_address (str): Address the broker should respond to with
             updates.
            route (str): Which route the Message will travel through.
            channel (str): which channel to add the transformer to.
            address (str): Where the channel should forward the data to.
        """
        super().__init__(OBJ_TRANSFORMER)
        self.cmd_type = CMD_ADD
        self.return_address = return_address
        self.arg1 = route
        self.arg2 = channel
        self.arg3 = address

    @property
    def cmd_valid(self) -> bool:
        return self.cmd_type in (CMD_ADD, CMD_REMOVE)


class Subscriber(_MyceliaObj):
    def __init__(self,
                 return_address: str,
                 route: str,
                 channel: str,
                 address: str) -> None:
        """
        Args:
            return_address (str): Address the broker should respond to with
             updates.
            route (str): Which route the Message will travel through.
            channel (str): which channel to add the subscriber to.
            address (str): Where the channel should forward the data to.
        """
        super().__init__(OBJ_SUBSCRIBER)
        self.cmd_type = CMD_ADD
        self.return_address = return_address
        self.arg1 = route
        self.arg2 = channel
        self.arg3 = address

    @property
    def cmd_valid(self) -> bool:
        return self.cmd_type in (CMD_ADD, CMD_REMOVE)


class GlobalValues(object):
    """The data struct that the broker should update values from.
    Only change the values that you need.
    """
    address: str = ''
    port: int = -1
    verbosity: int = -1
    print_tree: Optional[bool] = None
    transform_timeout: str = ''
    consolidate: Optional[bool] = None
    security_token: str = ''


class Globals(_MyceliaObj):
    def __init__(self, return_address: str, payload: GlobalValues) -> None:
        """
        Args:
            return_address (str): Address the broker should respond to with
             updates.
            payload (GlobalValues): The struct object mycelia.GlobalValues that
             contains the updated values.
        """
        super().__init__(OBJ_GLOBALS)
        self.cmd_type = CMD_UPDATE
        self.return_address = return_address

        data = {}
        if payload.address != '':
            data['address'] = payload.address
        if 0 < payload.port < 65536:
            data['port'] = payload.port
        if -1 < payload.verbosity < 4:
            data['verbosity'] = payload.verbosity
        if type(payload.print_tree) is bool:
            data['print_tree'] = payload.print_tree
        if payload.transform_timeout != '':
            data['transform_timeout'] = payload.transform_timeout
        if type(payload.consolidate) is bool:
            data['consolidate'] = payload.consolidate
        if payload.security_token == '':
            raise MissingSecurityTokenError()
        else:
            data['security-token'] = payload.security_token

        if not data:
            raise ValueError('No valid GlobalValues were added.')

        self.payload = json.dumps(data)

    @property
    def cmd_valid(self) -> bool:
        return self.cmd_type == CMD_UPDATE


class Action(_MyceliaObj):
    def __init__(self, return_address: str) -> None:
        """
        Args:
            return_address (str): Address the broker should respond to with
             updates.
        """
        super().__init__(OBJ_ACTION)
        self.cmd_type = _CMD_UNKNOWN
        self.return_address = return_address

    @property
    def cmd_valid(self) -> bool:
        return self.cmd_type in (CMD_SIGTERM,)


# --------Message Handling-----------------------------------------------------

def _u8(n: int) -> bytes:
    """Pack unsigned 8-bit int."""
    return struct.pack('>B', n & 0xFF)


def _u16(n: int) -> bytes:
    """Pack unsigned 16-bit int."""
    return struct.pack('>H', n & 0xFFFF)


def _u32(n: int) -> bytes:
    """Pack unsigned 32-bit int as big-endian."""
    return struct.pack('>I', n & 0xFFFFFFFF)


def _pstr8(s: str) -> bytes:
    """Length-prefixed string: [u8 len][bytes]."""
    b = s.encode(_ENCODING)
    return _u8(len(b)) + b


def _pstr16(s: str) -> bytes:
    """Length-prefixed string: [u16 len][bytes]."""
    b = s.encode(_ENCODING)
    return _u16(len(b)) + b


def _pstr32(s: str) -> bytes:
    """Length-prefixed string: [u32 len][bytes]."""
    b = s.encode(_ENCODING)
    return _u32(len(b)) + b


def _pbytes16(b: bytes) -> bytes:
    """Length-prefixed bytes: [u16 len][bytes]."""
    bb = bytes(b)
    return _u16(len(bb)) + bb


def _encode_mycelia_obj(obj: _MyceliaObj) -> bytes:
    if not obj.cmd_valid:
        raise ValueError(f'Message command {obj.cmd_type} not permissible!')

    out = bytearray()

    # -----Fixed Header-----
    out += _u8(obj.protocol_version)
    out += _u8(obj.obj_type)
    out += _u8(obj.cmd_type)

    # -----Tracking Sub-Header-----
    out += _pstr8(str(uuid.uuid4()))
    if obj.return_address == '':
        raise ValueError("Message is missing sender's address!")
    out += _pstr16(obj.return_address)

    # -----Command Arguments-----
    needs_args = (OBJ_MESSAGE, OBJ_SUBSCRIBER, OBJ_TRANSFORMER)
    if obj.obj_type in needs_args and obj.arg1 == '':
        raise ValueError(f'Message has incomplete args!')
    out += _pstr8(obj.arg1)
    out += _pstr8(obj.arg2)
    out += _pstr8(obj.arg3)
    out += _pstr8(obj.arg4)

    # -----Payload-----
    out += _pbytes16(obj.payload.encode(_ENCODING))

    packet_bytes = bytes(out)
    packet = _u32(len(packet_bytes)) + packet_bytes

    return packet


def send(message: _MyceliaObj, address: str, port: int) -> None:
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
            except KeyboardInterrupt:
                print('Exiting on keyboard interrupt.')
                return

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
