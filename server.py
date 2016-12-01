#!/usr/bin/env python3

import asyncio
import aiofiles
from network import *

async def sendfile(stream, fname, pos, size):
    async with aiofiles.open(fname, 'rb') as f:
        await f.seek(pos)
        while size > 0:
            buf_size = 4096 if size > 4096 else size
            buf = await f.read(buf_size)
            stream.write(buf)
            size -= buf_size

loop = asyncio.get_event_loop()

loop.run_until_complete(sendfile(None, 'proto_design.txt', 100, 800))
