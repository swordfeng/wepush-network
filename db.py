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
        CREATE TABLE messages IF NOT EXIST (devicekey TEXT, fromdevice TEXT, type TEXT, content_type TEXT, content TEXT, pushtime DATETIME, pushed BOOLEAN);
        CREATE INDEX IF NOT EXIST messages_devicekey_index ON messages (devicekey);
        CREATE TABLE fetching_files IF NOT EXIST (fromdevice TEXT, digest TEXT, length INTEGER, completed_ranges TEXT, PRIMARY KEY (fromdevice, digest));
        CREATE TABLE fetching_targets IF NOT EXIST (fromdevice TEXT, digest TEXT, target TEXT);
        CREATE INDEX IF NOT EXIST fetching_targets_index ON messages (fromdevice, digest);
        ''')


async def register_user(username, password):
    pass

async def register_device(username, password, devicekey):
    pass

async def get_device_user(devicekey):
    pass

async def get_user_device(username):
    pass

async def push_message(devicekeys, fromdevice, content_type, message):
    pass

async def push_file(devicekeys, fromdevice, content_type, digest):
    pass

async def get_fetching_list(fromdevice):
async def get_fetching(fromdevice, digest):
async def add_fetching(fromdevice, target, digest, length):
