import asyncio
from network import *

loop = asyncio.get_event_loop()

async def on_connect(stream):
    print('connection {}'.format(stream.peer_key()))
    while True:
        try:
            data = await stream.read()
        except NetworkClosedException:
            break
        stream.write(data)

server = loop.run_until_complete(listen(('0.0.0.0', 22345,), lambda stream: asyncio.ensure_future(on_connect(stream))))

loop.run_until_complete(server.wait_closed())
