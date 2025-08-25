from __future__ import annotations

import socket
import threading
import uuid
from typing import Callable
from typing import Union

__all__ = [
    'SendMessage',
    'AddSubscriber',
    'AddChannel',
    'AddRoute',
    'AddTransformer',
    'process_command',
    'get_local_ipv4',
    'MyceliaListener'
]

# Version 1 of the command API does not support sub-command parsing.
# The <object>.<action> syntax is the conform to future version feature syntax.
_CMD_SEND_MESSAGE = 'MESSAGE.SEND'
_CMD_ADD_ROUTE = 'ROUTE.ADD'
_CMD_ADD_CHANNEL = 'CHANNEL.ADD'
_CMD_ADD_TRANSFORMER = 'TRANSFORMER.ADD'
_CMD_ADD_SUBSCRIBER = 'SUBSCRIBER.ADD'

_TYPE_COMMAND = Union[
    _CMD_SEND_MESSAGE,
    _CMD_ADD_ROUTE,
    _CMD_ADD_CHANNEL,
    _CMD_ADD_TRANSFORMER,
    _CMD_ADD_SUBSCRIBER
]

_ENCODING = 'utf-8'
API_PROTOCOL_VER = 1


# --------Command Types--------------------------------------------------------

class CommandType(object):
    """A CommandType is the type of functionality you wish to invoke in the
    Mycelia instance, such as sending a message, registering a route,
    adding a channel to a route, or adding a subscriber to a route + channel.
    """


class SendMessage(CommandType):
    """A CommandType that will send a string message through the
    specified route.

    Args:
        route (str): The route to send the message through.
        payload (str): The data to forward to all subscribers.
        proto_ver (int): The protocol version, defaults to API_PROTOCOL_VER.
    """

    def __init__(self,
                 route: str,
                 payload: str,
                 proto_ver: int = API_PROTOCOL_VER) -> None:
        self.proto_ver: str = str(proto_ver)
        self.cmd_type: _TYPE_COMMAND = _CMD_SEND_MESSAGE
        self.id: str = str(uuid.uuid4())
        self.route: str = route
        self.payload: str = payload


class AddRoute(CommandType):
    """A CommandType that will register a route on a Mycelia instance.

    Args:
        name (str): The name of the route. Messages containing this name
         in their route field will be sent down channels in this route.
        proto_ver (int): The protocol version, defaults to API_PROTOCOL_VER.
    """

    def __init__(self,
                 name: str,
                 proto_ver: int = API_PROTOCOL_VER) -> None:
        self.proto_ver: str = str(proto_ver)
        self.cmd_type: _TYPE_COMMAND = _CMD_ADD_ROUTE
        self.id: str = str(uuid.uuid4())
        self.name = name


class AddChannel(CommandType):
    """A CommandType that will add a channel to a specified
    route.

    Args:
        route (str): The route to add the channel to.
        name (str): What to name the channel.
        proto_ver (int): The protocol version, defaults to API_PROTOCOL_VER.
    """

    def __init__(self,
                 route: str,
                 name: str,
                 proto_ver: int = API_PROTOCOL_VER) -> None:
        self.proto_ver: str = str(proto_ver)
        self.cmd_type: _TYPE_COMMAND = _CMD_ADD_CHANNEL
        self.id: str = str(uuid.uuid4())
        self.route = route
        self.name = name


class AddTransformer(CommandType):
    """A CommandType that will register a transformer on a route.

    Args:
        route (str): The route key that the subscriber will receive
         message from.
        channel (str): The channel name to subscribe to that exists
         on the given route.
        address (str): The address all messages should be forwarded
         to from the Mycelia server.
        proto_ver (int): The protocol version, defaults to API_PROTOCOL_VER.
    """

    def __init__(self,
                 route: str,
                 channel: str,
                 address: str,
                 proto_ver: int = API_PROTOCOL_VER) -> None:
        self.proto_ver: str = str(proto_ver)
        self.cmd_type: _TYPE_COMMAND = _CMD_ADD_TRANSFORMER
        self.id: str = str(uuid.uuid4())
        self.route = route
        self.channel = channel
        self.address = address


class AddSubscriber(CommandType):
    """A CommandType that will add a subscriber to a specified
    route + channel.

    Args:
        route (str): The route key that the subscriber will receive
         message from.
        channel (str): The channel name to subscribe to that exists
         on the given route.
        address (str): The address all messages should be forwarded
         to from the Mycelia server.
        proto_ver (int): The protocol version, defaults to API_PROTOCOL_VER.
    """

    def __init__(self,
                 route: str,
                 channel: str,
                 address: str,
                 proto_ver: int = API_PROTOCOL_VER) -> None:
        self.proto_ver: str = str(proto_ver)
        self.cmd_type: _TYPE_COMMAND = _CMD_ADD_SUBSCRIBER
        self.id: str = str(uuid.uuid4())
        self.route = route
        self.channel = channel
        self.address = address


# --------Message Handling-----------------------------------------------------

def _encode_uvarint(n: int) -> bytes:
    """Encode an unsigned integer as LEB128 (uvarint).
    Will convert n to absolute.

    Args:
        n (int): Non-negative integer to encode.
    Returns:
        bytes: LEB128-encoded unsigned varint.
    """
    n = abs(n)
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            break

    return bytes(out)


def _serialize_message(msg: CommandType) -> bytes:
    # Mainly a stub, could probably be removed, but I wanted a separate
    # location for string message assembly incase it ever changes.
    fields: list[str] = list(msg.__dict__.values())
    parts: list[bytes] = []
    for f in fields:
        body = f.encode(_ENCODING)
        if len(body) == 0:
            continue
        parts.append(_encode_uvarint(len(body)))
        parts.append(body)

    return b''.join(parts)


def process_command(message: CommandType, address: str, port: int) -> None:
    """Sends the CommandType message. The message type should be
    `mycelia.SendMessage`, `mycelia.AddSubscriber`, `mycelia.AddChannel`,
    or `mycelia.AddRoute`.
    """
    payload = _serialize_message(message)
    frame = _encode_uvarint(len(payload)) + payload

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
                 message_processor: Callable[[bytes], None],
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
                break  # Socket was closed

            with conn:
                print(f'Connected by {addr}')
                while not self._stop_event.is_set():
                    try:
                        payload = conn.recv(1024)
                    except OSError:
                        break

                    if not payload:
                        break

                    self._message_processor(payload)

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
