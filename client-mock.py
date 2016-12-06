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
                self.last_heartbeat = datetime.today()
        except BaseException as e:
            print(e)
            stream.close()

client = ClientEndpoint(('127.0.0.1', 12345))

async def init():
    task = asyncio.ensure_future(client.daemon())
    await asyncio.sleep(1)
    stream = await connect(('127.0.0.1', 12345))
    sendjson(stream, {'message': 'status'})
    print(await readjson(stream))
    sendjson(stream, {'message': 'push', 'content_type': 'text/plain', 'content': 'testtext', 'target': ['FioVevEmxSnYFyvs1cxWakudeRpqK8f9mw3z3Y1HRvg=']})
    print(await readjson(stream))
    sendjson(stream, {'message': 'push_file', 'content_type': 'text/plain', 'target': ['FioVevEmxSnYFyvs1cxWakudeRpqK8f9mw3z3Y1HRvg='],
        'filename': 'proto_design.txt', 'length': 5360, 'digest': '87334a310d1cb6a985b11291212b6c8feabd1f20b0a2c40cd668261ab84eb66d'})
    r = await readjson(stream)
    print(r)
    if 'get_range' in r:
        await sendfile(stream, 'proto_design.txt', r['get_range'][0], r['get_range'][1])
        print(await readjson(stream))
    sendjson(stream, {'message': 'get_file', 'from': 'FioVevEmxSnYFyvs1cxWakudeRpqK8f9mw3z3Y1HRvg=',
        'digest': '87334a310d1cb6a985b11291212b6c8feabd1f20b0a2c40cd668261ab84eb66d', 'get_range': [0, 5360]})
    print(await readjson(stream))
    await recvfile(stream, 'proto.tmp', 0, 5360)
    await task

loop.run_until_complete(init())
