#!/usr/bin/python3

import asyncio
from network import *
from netutil import *

class ClientEndpoint():
    def __init__(self, server_addr):
        self.server_addr = server_addr
        self.last_heartbeat = None
        self.stream = None
        asyncio.ensure_future(daemon())
    async def daemon(self):
        while True:
            try:
                if self.last_heartbeat == None:
                    self.stream = await connect(server_addr)
                    self.listener = asyncio.ensure_future(listen(self.stream))
                    self.last_heartbeat = datetime.today()
                elif datetime.today() - self.last_heartbeat > datetime.timedelta(seconds=60):
                    self.listener.cancel()
                    self.stream = await connect(server_addr)
                    self.listener = asyncio.ensure_future(listen(self.stream))
                    self.last_heartbeat = datetime.today()
            finally:
                await asyncio.sleep(30)
    async def listen(self, stream):
        try:
            while True:
                request = await readjson(stream)
        except BaseException as e:
            print(e)
            stream.close()
