#!/usr/bin/python3

import sqlite3

db = sqlite3.connect('data.db', detect_types=sqlite3.PARSE_DECLTYPES)
c = db.cursor()
c.execute('''
CREATE TABLE users IF NOT EXIST (username TEXT PRIMARY KEY, password TEXT);
CREATE TABLE devices IF NOT EXIST (devicekey TEXT PRIMARY KEY, username TEXT, description TEXT);
CREATE INDEX IF NOT EXIST devices_username_index ON devices (username);
CREATE TABLE messages IF NOT EXIST (devicekey TEXT, fromdevice TEXT, type TEXT, content_type TEXT, content TEXT, pushtime DATETIME, pushed BOOLEAN);
CREATE INDEX IF NOT EXIST messages_devicekey_index ON messages (devicekey);
CREATE TABLE fetching_files IF NOT EXIST (fromdevice TEXT, target TEXT, digest TEXT, length INTEGER, completed_ranges TEXT, PRIMARY KEY (fromdevice, digest));
''')
db.commit()

def register_user(username, password):
    pass

def register_device(username, password, devicekey):
    pass

def get_device_user(devicekey):
    pass

def get_user_device(username):
    pass

def push_message(devicekeys, fromdevice, message):
    pass

def push_file(devicekeys, fromdevice, digest):
    pass
