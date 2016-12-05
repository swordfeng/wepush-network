#!/usr/bin/python3

import asyncio
import aioodbc
import json

loop = asyncio.get_event_loop()

async def init():
    global db
    dsn = 'Driver=SQLite;Database=data.db'
    db = await aioodbc.connect(dsn=dsn, loop=loop)
    async with db.cursor() as c:
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
    async with db.cursor() as c:
        await c.execute('''
        INSERT INTO messages(devicekey, fromdevice, type, content_type, content, pushed)
        VALUES (?, ?, ?, ?, ?, 0)
        ''', target, fromdevice, 'text', content_type, content)
async def push_file(target, fromdevice, content_type, digest, length):
    content = json.dumps({
        'digest': digest,
        'length': length
    })
    async with db.cursor() as c:
        await c.execute('''
        INSERT INTO messages(devicekey, fromdevice, type, content_type, content, pushed)
        VALUES (?, ?, ?, ?, ?, 0)
        ''', target, fromdevice, 'file', content_type, content)

async def get_device_fetching(devicekey):
    async with db.cursor() as c:
        await c.execute('SELECT * FROM fetching_files WHERE fromdevice = ?', devicekey)
        return await c.fetchall()
async def get_fetching(devicekey, digest):
    async with db.cursor() as c:
        await c.execute('SELECT * FROM fetching_files WHERE fromdevice = ? AND digest = ?', devicekey, digest)
        return await c.fetchone()
async def add_fetching(devicekey, targets, filename, digest, length):
    async with db.cursor() as c:
        await c.execute('INSERT OR IGNORE INTO fetching_files VALUES (?, ?, ?, ?, 0)', devicekey, digest, filename, length)
        for target in targets:
            await c.execute('INSERT OR IGNORE INTO fetching_targets VALUES (?, ?, ?)', devicekey, digest, target)
async def set_fetching_completed(devicekey, digest, pos):
    async with db.cursor() as c:
        await c.execute('UPDATE fetching_files SET completed_size = ? WHERE fromdevice = ? AND digest = ?', pos, devicekey, digest)
async def cancel_fetching(devicekey, digest):
    async with db.cursor() as c:
        await c.execute('DELETE fetching_files WHERE fromdevice = ? AND digest = ?', devicekey, digest)
        await c.execute('DELETE fetching_targets WHERE fromdevice = ? AND digest = ?', devicekey, digest)

async def get_unpushed_messages(devicekey):
    async with db.cursor() as c:
        await c.execute('SELECT * FROM messages WHERE devicekey = ? AND pushed = 0', devicekey)
        return await c.fetchall()
async def set_message_pushed(mid):
    async with db.cursor() as c:
        await c.execute('UPDATE messages SET pushed = 1 WHERE mid = ?', mid)
