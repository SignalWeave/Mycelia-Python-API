# Mycelia-Python-API
Mycelia Python API

## Usage

Define a command type and then call `send(message)`.

### Basic Example

```python
import json

import mycelia


def main() -> None:
    payload = {'name': 'nate', 'age': 31, 'id': '16-70-18'}
    msg = mycelia.Message(
        return_address=mycelia.get_local_ipv4(),
        route='example_route',
        payload=json.dumps(payload)
    )

    mycelia.send_and_get_ack(
        message=msg,
        address='10.0.0.52',  # Broker address
        port=5000
    )


if __name__ == '__main__':
    main()
```


### Basic Messaging

```python
import json
import uuid

import mycelia

SERVER_ADDR = '10.0.0.52'
SERVER_PORT = 4400


def send_message() -> None:
    uid = str(uuid.uuid4())
    payload = {'name': 'nate', 'age': 31, 'id': uid}
    msg = mycelia.Message(
        return_address=mycelia.get_local_ipv4(),
        route='example_route',
        payload=json.dumps(payload)
    )
    msg.timeout = 1.0
    msg.ack_policy = mycelia.ACK_PLCY_ONSENT

    response = mycelia.send_and_get_ack(
        message=msg,
        address=SERVER_ADDR,
        port=SERVER_PORT
    )
    print(f'Response uid {response.uid}')
    print(f'Response ack {response.ack}')
```

### Basic Listening Service

```python
import json

import mycelia


LOCAL_HOST = '127.0.0.1'
LOCAL_PORT = 5500


def setup() -> None:
    """Adds the subscription to the route + channel."""
    msg_add_sub = mycelia.Subscriber(
        return_address=mycelia.get_local_ipv4(),
        route='example_route',
        channel='channel1',
        address=f'{LOCAL_HOST}:{LOCAL_PORT}'
    )
    mycelia.send_and_get_ack(
        message=msg_add_sub,
        address='10.0.0.52',
        port=5000
    )


def handle_message(payload: bytes) -> None:
    """What to do with incoming messages."""
    try:
        data = json.loads(payload.decode('utf-8'))
    except json.JSONDecodeError:
        data = payload.decode('utf-8')

    print('Received:', data)


def main() -> None:
    setup()
    listener = mycelia.MyceliaListener(handle_message, LOCAL_HOST, LOCAL_PORT)
    listener.start()


if __name__ == '__main__':
    main()
```
