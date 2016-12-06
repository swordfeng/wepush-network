#!/usr/bin/python3

import aiofiles
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib

def fnencode(b64code):
    result = ''
    for c in b64code:
        if c == 'i':
            result += 'ia'
        elif c == '+':
            result += 'ib'
        elif c == '/':
            result += 'ic'
        else:
            result += c
    return result

def fndecode(fncode):
    result = ''
    shift = False
    for c in fncode:
        if shift:
            if c == 'a':
                result += 'i'
            elif c == 'b':
                result += '+'
            elif c == 'c':
                result += '/'
            else:
                raise Exception('invalid code')
            shift = False
        else:
            if c == 'i':
                shift = True
            else:
                result += c
    return result

filedir = 'files'
loop = asyncio.get_event_loop()
pool = ThreadPoolExecutor(4)

def do_digest(path):
    h = hashlib.new('sha256')
    with open(path, 'rb') as f:
        while True:
            buf = f.read(4096)
            if len(buf) == 0:
                break
            h.update(buf)
    return h.hexdigest()

def file_path(devicekey, digest):
    return filedir + '/' + fnencode(devicekey) + '_' + digest
def file_exist(devicekey, digest):
    path = file_path(devicekey, digest)
    return os.path.exists(path)
async def file_create(devicekey, digest, length):
    path = file_path(devicekey, digest)
    async with aiofiles.open(path, 'ab') as f:
        f.truncate(length)
    return path
async def file_verify_digest(devicekey, digest):
    path = file_path(devicekey, digest)
    if not os.path.exists(path):
        return False
    return digest.lower() == await loop.run_in_executor(pool, do_digest, path)
def file_remove(devicekey, digest):
    path = file_path(devicekey, digest)
    os.remove(path)
