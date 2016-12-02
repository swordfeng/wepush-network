#!/usr/bin/env python3

import asyncio
import aiofiles
from network import *
from netutil import *
import db
import fm

loop = asyncio.get_event_loop()

handlers = {
    'listen': handle_listen,
    'push': handle_push,
    'push_file': handle_push_file
}

async def on_connection(stream):
    while True:
        try:
            request = await readjson(stream)
        except:
            stream.close()
            return
        if not 'message' in request:
            stream.close()
            return
        if not await handlers[request['messge']](stream, request):
            # ownership transfered to handler
            break

listeners = {}
async def handle_listen(stream, request):
    sendjson(stream, {'success': True})
    devicekey = stream.peer_key()
    if devicekey in listeners:
        listeners[devicekey] = []
    heartbeat_task = asyncio.ensure_future(heartbeat(stream))
    listeners[devicekey].append(stream)
    # push unpushed messages
    device_push_messages(devicekey)
    # restart unfetched files
    for fileinfo in await db.get_device_fetchlist(devicekey):
        try_restart_file(fileinfo)
    return True

async def heartbeat(stream):
    try:
        while True:
            await asyncio.sleep(30)
            sendjson(stream, {'message': 'heartbeat'})
            await readjson(stream)
    except NetworkClosedException:
        devicekey = stream.peer_key()
        ls = listeners[devicekey]
        for i in range(0, len(ls)):
            if ls[i] == stream:
                del ls[i]
    finally:
        stream.close()

async def handle_push(stream, request):
    # insert message into database
    for devicekey in request['target']:
        await db.push_message(devicekey, stream.peer_key(), request['content_type'], request['content'])
        device_push_messages(devicekey)
    sendjson(stream, {'success': True})

async def handle_push_file(stream, request):
    devicekey = stream.peer_key()
    # add file to fetching_files if not added and (file not exist or digest mismatch)
    fileinfo = None
    path = await file_path(devicekey, request['digest'])
    if path == None:
        fileinfo = await db.add_fetching(devicekey, request['target'], request['digest'], request['length'])
        path = await fm.file_create(devicekey, request['digest'])
    if fileinfo == None:
        # fetch is already finished
        request['fromdevice'] = devicekey
        await finish_send_file(request)
        sendjson(stream, {'success': True})
    else:
        # we need fetch
        try:
            await do_fetch_file(stream, fileinfo)
            await finish_send_file(fileinfo)
            sendjson(stream, {'success': True})
        except NetworkClosedException:
            try_restart_file(fileinfo)

async def finish_send_file(fileinfo):
    for devicekey in fileinfo['target']:
        await db.push_file(devicekey, fileinfo['fromdevice'], fileinfo['content_type'], fileinfo['digest'])
        device_push_messages(devicekey)

pushing_messages = set()
async def device_push_messages_async(devicekey):
    if devicekey in pushing_messages:
        return
    pushing_messages.add(devicekey)
    messages = await db.get_unpushed_messages(devicekey)
    if devicekey not in listeners:
        return
    for message in messages:
        if len(listeners[devicekey]) == 0:
            return
        stream = random.choice(listeners[devicekey])
        try:
            if message.type == 'text':
                sendjson(stream, {
                    'message': 'push',
                    'content_type': message['content_type'],
                    'content': message['content']
                })
            elif message.type == 'file':
                sendjson(stream, {
                    'message': 'push_file',
                    'content_type': message['content_type'],
                    'filename': message['filename'],
                    'length': message['length'],
                    'digest': message['digest']
                })
            result = await readjson(stream)
            if result['success']:
                await db.message_pushed(message.mid)
        except Exception as e:
            print(e)
            # ??
    pushing_messages.discard(devicekey)

def device_push_messages(devicekey):
    asyncio.ensure_future(device_push_messages_async(devicekey))

def do_fetch_file(stream, fileinfo):
def try_restart_file(fileinfo):

server = loop.run_until_complete(listen(('0.0.0.0', 12345), lambda stream: asyncio.ensure_future(on_connection(stream))))
print('Server listening on 0.0.0.0:12345')

try:
    loop.run_until_complete(server.wait_closed())
except KeyboardInterrupt:
    print('Exiting server...')
    server.close()
    loop.run_until_complete(server.wait_closed())
