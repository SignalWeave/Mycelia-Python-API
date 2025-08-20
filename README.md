# Mycelia-Python-API
Mycelia Python API

## Usage

Define a command type and then call `process_command(cmd)`.

### Basic Example

```python
import json

import mycelia


SERVER_ADDR = '127.0.0.1'
SERVER_PORT = 5000


# -----Send Message------------------------------------------------------------

data = {'name': 'Nate', 'age': 31}
cmd = mycelia.SendMessage('route_name', json.dumps(data))
mycelia.process_command(cmd, SERVER_ADDR, SERVER_PORT)


# -----Add Channel-------------------------------------------------------------

cmd = mycelia.AddChannel('route_name', 'new_channel')
mycelia.process_command(cmd, SERVER_ADDR, SERVER_PORT)


# -----Add Route---------------------------------------------------------------

cmd = mycelia.AddRoute('new_route_name')
mycelia.process_command(cmd, SERVER_ADDR, SERVER_PORT)


# -----Add Subscriber----------------------------------------------------------

cmd = mycelia.AddSubscriber('route_name', 'channel_name', '127.0.0.1:5500')
mycelia.process_command(cmd, SERVER_ADDR, SERVER_PORT)
```

### Basic Listening Service

```python
import json
import sys

import mycelia


def setup() -> None:
    """Adds appropriate routes + channels + subscribers to the message broker."""
    msg_add_route = mycelia.AddRoute('example_route')
    mycelia.process_command(msg_add_route, '10.0.0.52', 5000)

    msg_add_chan = mycelia.AddChannel('example_route', 'channel1')
    mycelia.process_command(msg_add_chan, '10.0.0.52', 5000)

    msg_add_sub = mycelia.AddSubscriber('example_route', 'channel1', f'127.0.0.1:5500')
    mycelia.process_command(msg_add_sub, '10.0.0.52', 5000)

    
def handle_message(payload: bytes) -> None:
    """What to do with incoming messages."""
    try:
        data = json.loads(payload.decode('utf-8'))
    except json.JSONDecodeError:
        data = payload.decode('utf-8')

    print('Received:', data)

    
def main() -> int:
    setup()
    listener = mycelia.MyceliaListener(handle_message, '127.0.0.1', 5500)
    listener.start()
    return 0


if __name__ == '__main__':
    sys.exit(main())
```
