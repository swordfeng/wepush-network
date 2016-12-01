#!/usr/bin/python3

from pysodium import *

sodium.crypto_hash_sha512.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulonglong]
def crypto_hash_sha512(data):
    assert type(data) == bytes
    result = ctypes.create_string_buffer(64)
    ret = sodium.crypto_hash_sha512(result, data, len(data))
    assert ret == 0
    return result.raw

class Nonce:
    def __init__(self, size):
        self.nonce = bytearray(b'\x00' * size)
    def get(self):
        result = bytes(self.nonce)
        for i in range(0, len(self.nonce)):
            self.nonce[i] += 1
            if self.nonce[i] != 0:
                break
        return result
