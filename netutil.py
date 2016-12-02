#!/usr/bin/python3

import asyncio
import aiofiles
import json

async def sendfile(stream, fname, pos, size):
    len_write = 0
    async with aiofiles.open(fname, 'rb') as f:
        await f.seek(pos)
        while size > 0:
            buf_size = 4096 if size > 4096 else size
            buf = await f.read(buf_size)
            if len(buf) != buf_size:
                raise Exception('file size mismatch!')
            try:
                stream.write(buf)
            except Exception as e:
                print('stream write interrupt:', e)
                return len_write
            size -= buf_size
            len_write += buf_size
            await stream.drain()

async def recvfile(stream, fname, pos, size):
    len_read = 0
    async with aiofiles.open(fname, 'wb') as f:
        await f.seek(pos)
        while size > 0:
            try:
                buf = await stream.read()
            except Exception as e:
                print('stream read interrupt:', e)
                return len_read
            buf_len = len(buf)
            await f.write(buf)
            len_read += buf_len
            size -= buf_len
            assert size >= 0
    return len_read

def sendjson(stream, obj):
    buf = json.dumps(obj).encode()
    stream.write(buf)

async def readjson(stream):
    buf = await stream.read()
    return json.loads(buf.decode())
