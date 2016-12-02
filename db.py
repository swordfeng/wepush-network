#!/usr/bin/python3

import asyncio
import aioodbc

loop = asyncio.get_event_loop()

async def init():
    global db
    dsn = 'Driver=SQLite;Database=data.db'
    db = await aioodbc.connect(dsn=dsn, loop=loop)
    async with db.cursor() as c:
        await c.execute('''
        CREATE TABLE users IF NOT EXIST (username TEXT PRIMARY KEY, password TEXT);
        CREATE TABLE devices IF NOT EXIST (devicekey TEXT PRIMARY KEY, username TEXT, description TEXT);
        CREATE INDEX IF NOT EXIST devices_username_index ON devices (username);
        CREATE TABLE messages IF NOT EXIST (mid INTEGER PRIMARY KEY ASC, devicekey TEXT, fromdevice TEXT, type TEXT, content_type TEXT, content TEXT, pushtime DATETIME, pushed BOOLEAN);
        CREATE INDEX IF NOT EXIST messages_devicekey_pushed_index ON messages (devicekey, pushed);
        CREATE TABLE fetching_files IF NOT EXIST (fromdevice TEXT, digest TEXT, filename TEXT, length INTEGER, completed_size INTEGER, PRIMARY KEY (fromdevice, digest));
        CREATE TABLE fetching_targets IF NOT EXIST (fromdevice TEXT, digest TEXT, target TEXT);
        CREATE INDEX IF NOT EXIST fetching_targets_index ON messages (fromdevice, digest);
        ''')
