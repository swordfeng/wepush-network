#!/usr/bin/env python3

import asyncio
import aiofiles
import random
from network import *
from netutil import *
import db
import fm

loop = asyncio.get_event_loop()

handlers = {}
async def on_connection(stream):
    print('new connection: {}'.format(stream.peer_key()))
    while True:
        try:
            request = await readjson(stream)
            print('{} requests: {}'.format(stream.peer_key(), request))
        except:
            stream.close()
            return
        if 'message' not in request:
            stream.close()
            return
        if await handlers[request['message']](stream, request):
            # ownership transfered to handler
            break

listeners = {}
async def handle_listen(stream, request):
    print('{} listening'.format(stream.peer_key()))
    sendjson(stream, {'success': True})
    devicekey = stream.peer_key()
    if devicekey not in listeners:
        listeners[devicekey] = set()
    heartbeat_task = asyncio.ensure_future(heartbeat(stream))
    listeners[devicekey].add(stream)
    # push unpushed messages
    device_push_messages(devicekey)
    # restart unfetched files
    for fileinfo in await db.get_device_fetching(devicekey):
        try_restart_file(fileinfo)
    return True

async def heartbeat(stream):
    try:
        while True:
            await asyncio.sleep(30)
            sendjson(stream, {'message': 'heartbeat'})
            await readjson(stream)
            print('{} heartbeat'.format(stream.peer_key()))
    except NetworkClosedException:
        devicekey = stream.peer_key()
        print('{} lost connection'.format(devicekey))
        listeners[devicekey].discard(stream)
    finally:
        #stream.close()
        pass

async def handle_push(stream, request):
    # insert message into database
    for devicekey in request['target']:
        await db.push_message(devicekey, stream.peer_key(), request['content_type'], request['content'])
        device_push_messages(devicekey)
    sendjson(stream, {'success': True})

async def handle_push_file(stream, request):
    devicekey = stream.peer_key()
    # add file to fetching_files if not added and (file not exist or digest mismatch)
    fileinfo = await db.get_fetching(devicekey, request['digest'])
    if fm.file_exist(devicekey, request['digest']) and fileinfo == None:
        # file already fetched
        fileinfo = request
        fileinfo['fromdevice'] = devicekey
    else:
        # may update targets
        fileinfo = await db.add_fetching(devicekey, request['target'], request['filename'], request['digest'], request['length'])
        path = await fm.file_create(devicekey, request['digest'], request['length'])
        try:
            startpos = fileinfo['completed_size']
            length = fileinfo['length']
            size = length - startpos
            if size > 0:
                sendjson(stream, {
                    'success': True,
                    'get_range': [startpos, length]
                })
                recv_size = await recvfile(stream, path, startpos, size)
                startpos += recv_size
            if startpos < length:
                await db.set_fetching_completed(fileinfo['fromdevice'], fileinfo['digest'], startpos)
            else:
                if not await fm.file_verify_digest(fileinfo['fromdevice'], fileinfo['digest']):
                    # cancel fetch
                    fm.file_remove(devicekey, fileinfo['digest'])
                    await db.cancel_fetching(devicekey, fileinfo['digest'])
                    raise Exception('file digest mismatch')
        except Exception as e:
            print('error when fetching file:', e)
            try_restart_file(fileinfo)
            sendjson(stream, {'success': False, 'error': 'fail to fetch'})
            return
    sendjson(stream, {'success': True})
    for devicekey in fileinfo['target']:
        await db.push_file(devicekey, fileinfo['fromdevice'], fileinfo['content_type'], fileinfo['digest'], fileinfo['length'], fileinfo['filename'])
        device_push_messages(devicekey)

async def handle_get_file(stream, request):
    if not fm.file_exist(request['from'], request['digest']):
        sendjson(stream, {
            'success': False,
            'error': 'file not exist'
        })
        return
    path = fm.file_path(request['from'], request['digest'])
    [start, end] = request['get_range']
    await sendfile(stream, path, start, end - start)

async def handle_status(stream, request):
    username = await db.get_user(stream.peer_key())
    result = {'registered': False}
    if username != None:
        result['registered'] = True
        result['username'] = username
        result['devices'] = await db.get_devices(username)
    sendjson(stream, result)

async def handle_register_device(stream, request):
    try:
        await db.register_device(stream.peer_key(), request['description'], request['username'], request['password'])
        sendjson(stream, {'success': True})
    except db.AuthError:
        sendjson(stream, {'success': False, 'error': 'invalid username or password'})
    except:
        sendjson(stream, {'success': False, 'error': 'failed to register device'})

async def handle_register_user(stream, request):
    print('{} register user {}'.format(stream.peer_key(), request['username']))
    try:
        await db.register_user(request['username'], request['password'])
    except BaseException:
        sendjson(stream, {'success': False, 'error': 'failed to register'})
        return
    await db.register_device(stream.peer_key(), request['description'], request['username'], request['password'])
    sendjson(stream, {'success': True})

pushing_messages = set()
async def device_push_messages_async(devicekey):
    if devicekey in pushing_messages:
        return
    pushing_messages.add(devicekey)
    print('start pushing for {}'.format(devicekey))
    messages = await db.get_unpushed_messages(devicekey)
    if devicekey not in listeners:
        return
    stream = random.choice(tuple(listeners[devicekey]))
    for message in messages:
        if len(listeners[devicekey]) == 0:
            return
        try:
            if message['type'] == 'text':
                sendjson(stream, {
                    'message': 'push',
                    'content_type': message['content_type'],
                    'content': message['content']
                })
            elif message['type'] == 'file':
                sendjson(stream, {
                    'message': 'push_file',
                    'content_type': message['content_type'],
                    'filename': message['filename'],
                    'length': message['length'],
                    'digest': message['digest']
                })
            result = await readjson(stream)
            if result['success']:
                await db.set_message_pushed(message['mid'])
        except NetworkClosedException:
            listeners[devicekey].discard(stream)
            return await device_push_messages_async(devicekey)
        except Exception as e:
            print(e)
            # ??
    pushing_messages.discard(devicekey)

def device_push_messages(devicekey):
    asyncio.ensure_future(device_push_messages_async(devicekey))

async def try_restart_file_async(fileinfo):
    devicekey = fileinfo['fromdevice']
    if devicekey not in listeners:
        return
    if len(listeners[devicekey]) == 0:
        return
    stream = random.choice(tuple(listeners[devicekey]))
    sendjson(stream, {
        'message': 'restart_file',
        'digest': fileinfo['digest']
    })
    result = await readjson(stream)
    if not result['success']:
        print('restart sending error:', result['error'])
        await db.cancel_fetching(fileinfo['fromdevice'], fileinfo['digest'])

def try_restart_file(fileinfo):
    asyncio.ensure_future(try_restart_file_async(fileinfo))

handlers = {
    'listen': handle_listen,
    'push': handle_push,
    'push_file': handle_push_file,
    'get_file': handle_get_file,
    'status': handle_status,
    'register_user': handle_register_user,
    'register_device': handle_register_device
}

loop.run_until_complete(db.init())

server = loop.run_until_complete(listen(('0.0.0.0', 12345), lambda stream: asyncio.ensure_future(on_connection(stream))))
print('Server listening on 0.0.0.0:12345')

try:
    loop.run_until_complete(server.wait_closed())
except KeyboardInterrupt:
    print('Exiting server...')
    server.close()
    loop.run_until_complete(server.wait_closed())
