#!/usr/bin/python3

import asyncio
import aioodbc
import json
from pysodium import *

loop = asyncio.get_event_loop()

async def init():
    global db
    dsn = 'Driver=SQLite;Database=data.db'
    db = await aioodbc.create_pool(dsn=dsn, loop=loop, autocommit=True)
    async with db.acquire() as conn:
        async with conn.cursor() as c:
            await c.execute('''
            CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT);
            CREATE TABLE IF NOT EXISTS devices (devicekey TEXT PRIMARY KEY, username TEXT, description TEXT);
            CREATE INDEX IF NOT EXISTS devices_username_index ON devices (username);
            CREATE TABLE IF NOT EXISTS messages (mid INTEGER PRIMARY KEY ASC, devicekey TEXT, fromdevice TEXT, type TEXT, content_type TEXT, content TEXT, pushed INTEGER);
            CREATE INDEX IF NOT EXISTS messages_devicekey_pushed_index ON messages (devicekey, pushed);
            CREATE TABLE IF NOT EXISTS fetching_files (fromdevice TEXT, digest TEXT, filename TEXT, length INTEGER, completed_size INTEGER, PRIMARY KEY (fromdevice, digest));
            CREATE TABLE IF NOT EXISTS fetching_targets (fromdevice TEXT, digest TEXT, target TEXT, UNIQUE (fromdevice, digest, target));
            CREATE INDEX IF NOT EXISTS fetching_targets_index ON fetching_targets (fromdevice, digest);
            ''')

def __init__():
    loop.run_until_complete(init())

async def push_message(target, fromdevice, content_type, content):
    async with db.acquire() as conn:
        async with conn.cursor() as c:
            await c.execute('''
            INSERT INTO messages(devicekey, fromdevice, type, content_type, content, pushed)
            VALUES (?, ?, ?, ?, ?, 0)
            ''', target, fromdevice, 'text', content_type, content)
async def push_file(target, fromdevice, content_type, digest, length, filename):
    content = json.dumps({
        'digest': digest,
        'length': length,
        'filename': filename
    })
    async with db.acquire() as conn:
        async with conn.cursor() as c:
            await c.execute('''
            INSERT INTO messages(devicekey, fromdevice, type, content_type, content, pushed)
            VALUES (?, ?, ?, ?, ?, 0)
            ''', target, fromdevice, 'file', content_type, content)

async def get_device_fetching(devicekey):
    async with db.acquire() as conn:
        async with conn.cursor() as c:
            await c.execute('SELECT * FROM fetching_files WHERE fromdevice = ?', devicekey)
            result = []
            for t in await c.fetchall():
                result.append({
                    'fromdevice': t[0],
                    'digest': t[1],
                    'filename': t[2],
                    'length': t[3],
                    'completed_size': t[4]
                })
            return result
async def get_fetching(devicekey, digest):
    async with db.acquire() as conn:
        async with conn.cursor() as c:
            await c.execute('SELECT * FROM fetching_files WHERE fromdevice = ? AND digest = ?', devicekey, digest)
            t = await c.fetchone()
            if t != None:
                t = {
                    'fromdevice': t[0],
                    'digest': t[1],
                    'filename': t[2],
                    'length': t[3],
                    'completed_size': t[4]
                }
            return t
async def add_fetching(devicekey, targets, filename, digest, length):
    async with db.acquire() as conn:
        async with conn.cursor() as c:
            await c.execute('INSERT OR IGNORE INTO fetching_files VALUES (?, ?, ?, ?, 0)', devicekey, digest, filename, length)
            for target in targets:
                await c.execute('INSERT OR IGNORE INTO fetching_targets VALUES (?, ?, ?)', devicekey, digest, target)
async def set_fetching_completed(devicekey, digest, pos):
    async with db.acquire() as conn:
        async with conn.cursor() as c:
            await c.execute('UPDATE fetching_files SET completed_size = ? WHERE fromdevice = ? AND digest = ?', pos, devicekey, digest)
async def cancel_fetching(devicekey, digest):
    async with db.acquire() as conn:
        async with conn.cursor() as c:
            await c.execute('DELETE fetching_files WHERE fromdevice = ? AND digest = ?', devicekey, digest)
            await c.execute('DELETE fetching_targets WHERE fromdevice = ? AND digest = ?', devicekey, digest)

async def get_unpushed_messages(devicekey):
    async with db.acquire() as conn:
        async with conn.cursor() as c:
            await c.execute('SELECT * FROM messages WHERE devicekey = ? AND pushed = 0', devicekey)
            result = []
            for t in await c.fetchall():
                r = {
                    'mid': t[0],
                    'devicekey': t[1],
                    'fromdevice': t[2],
                    'type': t[3],
                    'content_type': t[4]
                }
                if t[3] == 'file':
                    o = json.loads(t[5])
                    for i in o:
                        r[i] = o[i]
                else:
                    r['content'] = t[5]
                result.append(r)
            return result
async def set_message_pushed(mid):
    async with db.acquire() as conn:
        async with conn.cursor() as c:
            await c.execute('UPDATE messages SET pushed = 1 WHERE mid = ?', mid)

async def get_user(devicekey):
    async with db.acquire() as conn:
        async with conn.cursor() as c:
            await c.execute('SELECT username FROM devices WHERE devicekey = ?', devicekey)
            t = await c.fetchone()
            if t != None:
                t = t[0]
            return t

async def get_devices(username):
    async with db.acquire() as conn:
        async with conn.cursor() as c:
            await c.execute('SELECT devicekey, description FROM devices WHERE username = ?', username)
            t = await c.fetchone()
            return {'devicekey': t[0], 'description': t[1]}

async def register_user(username, password):
    hpass = crypto_pwhash_scryptsalsa208sha256_str(password, 10000, 10000).decode()
    async with db.acquire() as conn:
        async with conn.cursor() as c:
            await c.execute('INSERT INTO users VALUES (?, ?)', username, hpass)

async def register_device(devicekey, description, username, password):
    async with db.acquire() as conn:
        async with conn.cursor() as c:
            await c.execute('SELECT password FROM users WHERE username = ?', username)
            hpass = await c.fetchone()
        if hpass == None:
            raise AuthError
        hpass, = hpass
        try:
            crypto_pwhash_scryptsalsa208sha256_str_verify(hpass.encode(), password)
        except ValueError:
            raise AuthError
        async with conn.cursor() as c:
            await c.execute('INSERT INTO devices VALUES (?, ?, ?)', devicekey, username, description)

class AuthError(Exception):
    pass
