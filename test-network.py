#!/usr/bin/env python3

from network import *
from netutil import *
import asyncio

loop = asyncio.get_event_loop()
server = None

async def conn_handler(stream):
    print('new stream')
    while True:
        try:
            message = await stream.read()
            print('server recv message, size', len(message))
            stream.write(message)
        except NetworkClosedException:
            break
        except Exception as e:
            print('Exception:', e)
            stream.close()
            break

async def do_request():
    stream = await connect(('127.0.0.1', 12345))
    stream.write(b'hello')
    msg = await stream.read()
    print(msg)
    asyncio.ensure_future(sendfile(stream, 'proto_design.txt', 0, 4500))
    await recvfile(stream, 'proto_design.tmp', 0, 4500)
    stream.close()
    server.close()

async def main():
    global server
    server = await listen(('0.0.0.0', 12345), lambda stream: asyncio.ensure_future(conn_handler(stream)))
    asyncio.ensure_future(do_request())
    await server.wait_closed()

loop.run_until_complete(main())
