#!/usr/bin/python3

import asyncio
from network import *
from netutil import *
from datetime import datetime, timedelta

loop = asyncio.get_event_loop()

class ClientEndpoint():
    def __init__(self, server_addr):
        self.server_addr = server_addr
        self.last_heartbeat = None
        self.stream = None
    async def daemon(self):
        print('start daemon')
        while True:
            try:
                if self.last_heartbeat == None:
                    self.stream = await connect(self.server_addr)
                    self.listener = asyncio.ensure_future(self.listen(self.stream))
                    self.last_heartbeat = datetime.today()
                elif datetime.today() - self.last_heartbeat > timedelta(seconds=60):
                    self.listener.cancel()
                    self.stream = await connect(self.server_addr)
                    self.listener = asyncio.ensure_future(self.listen(self.stream))
                    self.last_heartbeat = datetime.today()
            except BaseException as e:
                print(e)
            finally:
                await asyncio.sleep(30)
    async def listen(self, stream):
        try:
            print('listen')
            sendjson(stream, {'message': 'listen'})
            result = await readjson(stream)
            print(result)
            while True:
                request = await readjson(stream)
                print(request)
                sendjson(stream, {'success': True})
        except BaseException as e:
            print(e)
            stream.close()

client = ClientEndpoint(('127.0.0.1', 12345))

async def init():
    task = asyncio.ensure_future(client.daemon())
    await asyncio.sleep(1)
    stream = await connect(('127.0.0.1', 12345))
    sendjson(stream, {'message': 'register_device', 'username': 'swordfeng', 'password': '123456', 'description': 'testdevice'})
    print(await readjson(stream))
    sendjson(stream, {'message': 'status'})
    print(await readjson(stream))
    await task

loop.run_until_complete(init())
