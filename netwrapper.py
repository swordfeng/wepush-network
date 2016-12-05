import sys
import threading
import asyncio
from network import *
import struct
import sys
import os

# todo: how to get key?

sys.stdin = os.fdopen(sys.stdin.fileno(), 'rb', 0)
sys.stdout = os.fdopen(sys.stdout.fileno(), 'wb', 0)

loop = asyncio.get_event_loop()

server_addr=('127.0.0.1', 12345)
class InputHandler(threading.Thread):
    def __init__(self, stream):
        self.stream = stream
        self.stopped = False
        super(InputHandler, self).__init__()
    def run(self):
        try:
            while not self.stopped:
                lenbuf = sys.stdin.read(2)
                if len(lenbuf) < 2:
                    break
                length, = struct.unpack('<H', lenbuf)
                message = sys.stdin.read(length)
                loop.call_soon_threadsafe(self.stream.write, message)
        finally:
            pass
    def stop(self):
        self.stopped = True

async def main():
    inputThread = None
    try:
        stream = await connect(server_addr)
        inputThread = InputHandler(stream)
        inputThread.start()
        while True:
            message = await stream.read()
            lenbuf = struct.pack('<H', len(message))
            sys.stdout.write(lenbuf + message)
    finally:
        if inputThread != None:
            inputThread.stop()

loop.run_until_complete(main())
