#!/usr/bin/env python3

import asyncio
from pysodium import *
import keys
import struct

# 0 - init
# 1 - client handshake
# 2 - server handshake
# 3 - client complete
class TCPProtocol(asyncio.Protocol):
    def __init__(self, is_server = False):
        self.is_server = is_server
    def connection_made(self, transport):
        self.transport = transport
        self.buffer = b''
        if self.is_server:
            self.handshake = 0
        else:
            # client launch handshake
            handshake_buf = b'\x01\x03\x02\x43\x82\x43' + keys.pk
            signature = crypto_sign_detached(handshake_buf, keys.sk)
            self.transport.write(handshake_buf + signature)
            self.handshake = 1
    def connection_lost(self, exc):
        pass
    def data_received(self, data):
        self.buffer = self.buffer + data
        if self.is_server:
            if self.handshake == 0:
                # parse client data
                if len(self.buffer) < 6 + keys.PK_SIZE + keys.SIGN_SIZE: # TODO: check the content of the header, calculate the correct length
                    return
                device_key = self.buffer[6:6 + keys.PK_SIZE]
                signature = self.buffer[6 + keys.PK_SIZE:6 + keys.PK_SIZE + keys.SIGN_SIZE]
                handshake_buf = self.buffer[:6 + keys.PK_SIZE]
                try:
                    crypto_sign_verify_detached(signature, handshake_buf, device_key)
                except:
                    # error verify signature
                    self.transport.close()
                    return
                #self.buffer = self.buffer[6 + keys.PK_SIZE + keys.SIGN_SIZE:]
                self.buffer = b'' # should have no more data
                kex_sk = randombytes(keys.KEX_SK_SIZE)
                kex_pk = crypto_scalarmult_base(key_sk)
                server_buf = b'\x43\x02\x82' + keys.pk + kex_pk
                server_sig = crypto_sign_detached(server_buf, keys.sk)
                self.kex_sk = kex_sk
                self.handshake = 2
            elif self.handshake == 2:
                # parse client data 2
                if len(self.buffer) < keys.KEX_PK_SIZE + keys.SIGN_SIZE:
                    return
                client_kex_pk = self.buffer[:keys.KEX_PK_SIZE]
                signature = self.buffer[keys.KEX_PK_SIZE:keys.KEX_PK_SIZE+keys.SIGN_SIZE]
                try:
                    crypto_sign_verify_detached(signature, handshake_buf, device_key)
                except:
                    # error verify signature
                    self.transport.close()
                    return
                shared_secret = crypto_scalarmult_curve25519_(self.kex_sk, client_kex_pk)
                key = crypto_sha256(shared_secret)
                del self.kex_sk
                self.buffer = self.buffer[keys.KEX_PK_SIZE+keys.SIGN_SIZE:]
                self.key = key
                self.handshake = 3
            else:
                # unpack data, and send to upper object
                while len(self.buffer) >= 4 + keys.TAG_SIZE + keys.NONCE_SIZE:
                    length, = struct.unpack('<I', self.buffer[:4])
                    if len(self.buffer) < 4 + keys.TAG_SIZE + keys.NONCE_SIZE + length:
                        return
                    tag = self.buffer[4:4+keys.TAG_SIZE]
                    nonce = self.buffer[4+keys.TAG_SIZE:4+keys.TAG_SIZE+keys.NONCE_SIZE]
                    msg = self.buffer[4+keys.TAG_SIZE+keys.NONCE_SIZE:4+keys.TAG_SIZE+keys.NONCE_SIZE+length]
                    self.buffer = self.buffer[4+keys.TAG_SIZE+keys.NONCE_SIZE+length:]
                    try:
                        crypto_aead_chacha20poly1305_decrypt_detached()
        else:
            if self.handshake == 1:
                # parse server data
                # or store data
                # then complete
                pass
            else:
                # unpack data, and send to upper object
                pass
    def eof_received(self):
        pass
    def write(data):
        # pack data with AEAD, write data
        pass

class UDPProtocol(asyncio.DatagramProtocol):
    def __init__(self):
        pass
    def connection_made(self, transport):
        pass
    def connection_lost(self, exc):
        pass
    def datagram_received(self, data, addr):
        pass
    def error_received(self, exc):
        pass

class WPProtocol:
    def set_write_function(write):
    def connection_made(self, peer_key):
    def connection_lost(self):
    def message_received(self, message):
    def eof_received(self):
    def send_message(self):

class WPTCPListener:
    def __init__(protocolFactory):
