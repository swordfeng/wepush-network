#!/usr/bin/python3

import asyncio
import aiofiles
import json

async def sendfile(stream, fname, pos, size):
    async with aiofiles.open(fname, 'rb') as f:
        await f.seek(pos)
        while size > 0:
            buf_size = 4096 if size > 4096 else size
            buf = await f.read(buf_size)
            if len(buf) != buf_size:
                raise Exception('file size mismatch!')
            stream.write(buf)
            size -= buf_size
            await stream.drain()

async def recvfile(stream, fname, pos, size):
    async with aiofiles.open(fname, 'wb') as f:
        await f.seek(pos)
        while size > 0:
            buf = await stream.read()
            buf_len = len(buf)
            await f.write(buf)
            print(buf_len, 'written')
            size -= buf_len
            print(size, 'remain')
            assert size >= 0

def sendjson(stream, obj):
    buf = json.dumps(obj).encode()
    stream.write(buf)

async def readjson(stream):
    buf = await stream.read()
    return json.loads(buf.decode())
