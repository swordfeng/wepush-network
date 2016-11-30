#!/usr/bin/python3

from pysodium import *

def crypto_hash_sha512(data):
    assert type(data) == bytes
    result = ctypes.create_string_buffer(64)
    ret = sodium.crypto_hash_sha512(result, data)
    assert ret == 0
    return result.raw
