# Mycelia-Python-Client
Mycelia Python Client

## Usage

Define a command type and then call `process_command(cmd)`.

### Example

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
