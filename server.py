#!/usr/bin/env python3

import asyncio
import aiofiles
from network import *
from netutil import *
from base64 import b64encode, b64decode

loop = asyncio.get_event_loop()

handlers = {
    'listen': handle_listen
}

async def on_connection(stream):
    while True:
        try:
            request = readjson(stream)
        except:
            stream.close()
            return
        if not 'message' in request:
            stream.close()
            return
        if not await handlers[request['messge']](stream, request):
            break

listeners = {}
async def handle_listen(stream, request):
    devicekey = b64encode(stream.peer_key())
    if devicekey in listeners:
        listeners[devicekey] = []
    heartbeat_task = asyncio.ensure_future(heartbeat(stream))
    listeners[devicekey].append(stream)
    # push unpushed messages
    # restart unfetched files

async def heartbeat(stream):
    try:
        while True:
            await asyncio.sleep(30)
            sendjson(stream, {'message': 'heartbeat'})
            await readjson(stream)
    except NetworkClosedException:
        devicekey = b64encode(stream.peer_key())
        ls = listeners[devicekey]
        for i in range(0, len(ls)):
            if ls[i] == stream:
                del ls[i]

async def handle_push(stream, request):
    # insert message into database
    # trigger message push process
    pass

async def handle_push_file(stream, request):
    # add file to fetching_files
    # start fetching file process (this process will do push after finish)
    pass

server = loop.run_until_complete(listen(('0.0.0.0', 12345), lambda stream: asyncio.ensure_future(on_connection(stream))))
print('Server listening on 0.0.0.0:12345')

try:
    loop.run_until_complete(server.wait_closed())
except KeyboardInterrupt:
    print('Exiting server...')
    server.close()
    loop.run_until_complete(server.wait_closed())
