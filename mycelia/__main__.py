import socket
import uuid
from typing import Union


__all__ = [
    'SendMessage',
    'AddSubscriber',
    'AddChannel',
    'AddRoute',
    'process_command'
]


_TYPE_SEND_MESSAGE = 'send_message'
_TYPE_ADD_SUBSCRIBER = 'add_subscriber'
_TYPE_ADD_CHANNEL = 'add_channel'
_TYPE_ADD_ROUTE = 'add_route'


_TYPE_COMMAND = Union[
    _TYPE_SEND_MESSAGE,
    _TYPE_ADD_SUBSCRIBER,
    _TYPE_ADD_CHANNEL,
    _TYPE_ADD_ROUTE
]

_DELIMITER = ';;'


# --------Command Types--------------------------------------------------------

class CommandType(object):
    """A CommandType is the type of functionality you wish to invoke in the
    Mycelia instance, such as sending a message, registering a route,
    adding a channel to a route, or adding a subscriber to a route + channel.
    """


class SendMessage(CommandType):
    """A CommandType that will send a string message through the
    specified route.

    Mycelia uses ;; as a delimiter token to split fields apart.
    Avoid using ;; in your route name or payload string.

    Args:
        route (str): The route to send the message through.

        payload (str): The data to forward to all subscribers.
    """
    def __init__(self, route: str, payload: str) -> None:
        self.cmd_type: _TYPE_COMMAND = _TYPE_SEND_MESSAGE
        self.id: str = str(uuid.uuid4())
        self.route: str = route
        self.payload: str = payload


class AddSubscriber(CommandType):
    """A CommandType that will add a subscriber to a specified
    route + channel.

    Mycelia uses ;; as a delimiter token to split fields apart.
    Avoid using ;; in your route name, channel name, or address.

    Args:
        route (str): The route key that the subscriber will receive
         message from.

        channel (str): The channel name to subscribe to that exists
         on the given route.

        address (str): The address all messages should be forwarded
         to from the Mycelia server.
    """
    def __init__(self, route: str, channel: str, address: str) -> None:
        self.cmd_type: _TYPE_COMMAND = _TYPE_ADD_SUBSCRIBER
        self.id: str = str(uuid.uuid4())
        self.route = route
        self.channel = channel
        self.address = address


class AddChannel(CommandType):
    """A CommandType that will add a channel to a specified
    route.

    Mycelia uses ;; as a delimiter token to split fields apart.
    Avoid using ;; in your route name or channel name.

    Args:
        route (str): The route to add the channel to.

        name (str): What to name the channel.
    """
    def __init__(self, route: str, name: str) -> None:
        self.cmd_type: _TYPE_COMMAND = _TYPE_ADD_CHANNEL
        self.id: str = str(uuid.uuid4())
        self.route = route
        self.name = name


class AddRoute(CommandType):
    """A CommandType that will register a route on a Mycelia instance.

    Mycelia uses ;; as a delimiter token to split fields apart.
    Avoid using ;; in your route name.

    Args:
        name (str): The name of the route. Messages containing this name
         in their route field will be sent down channels in this route.
    """
    def __init__(self, name: str) -> None:
        self.cmd_type: _TYPE_COMMAND = _TYPE_ADD_ROUTE
        self.id: str = str(uuid.uuid4())
        self.name = name


# --------Message Handling-----------------------------------------------------

def _serialize_message(msg: CommandType) -> str:
    # Mainly a stub, could probably be removed, but I wanted a separate location
    # for string assembled message assembly incase it ever changes.
    tokens = list(msg.__dict__.values())
    return _DELIMITER.join(tokens)


def process_command(message: CommandType, address: str, port: int) -> None:
    """Sends the CommandType message. The message type should be
    `mycelia.SendMessage`, `mycelia.AddSubscriber`, `mycelia.AddChannel`,
    or `mycelia.AddRoute`.
    """
    payload = _serialize_message(message)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((address, port))
        sock.sendall(payload.encode('utf-8'))
