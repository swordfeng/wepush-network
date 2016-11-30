#!/usr/bin/env python3

from network import *
import asyncio

loop = asyncio.get_event_loop()

async def conn_handler(stream):
    print('new stream')
    while True:
        try:
            message = await stream.read()
            print('server recv message', message)
            stream.write(message)
        except:
            stream.close()
            break

async def do_request():
    stream = await connect(('127.0.0.1', 12345))
    stream.write(b'hello')
    msg = await stream.read()
    print(msg)

async def main():
    server = await listen(('0.0.0.0', 12345), lambda stream: asyncio.ensure_future(conn_handler(stream)))
    asyncio.ensure_future(do_request())
    await server.wait_closed()

loop.run_until_complete(main())
