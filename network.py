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
    def __init__(self, is_server = False, protoFactory):
        self.is_server = is_server
        self.protoFactory = protoFactory
        self.proto = None
        self.close_exc = None
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
        if self.proto != None:
            if exc != None:
                self.proto.connection_lost(exc)
            else:
                self.proto.connection_lost(self.close_exc)
    def data_received(self, data):
        self.buffer = self.buffer + data
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
                self.close_exc = Exception('Invalid signature')
                self.transport.close()
                return
            #self.buffer = self.buffer[6 + keys.PK_SIZE + keys.SIGN_SIZE:]
            self.buffer = b'' # should have no more data
            kex_sk = randombytes(keys.KEX_SK_SIZE)
            kex_pk = crypto_scalarmult_curve25519_base(key_sk)
            server_buf = b'\x43\x02\x82' + keys.pk + kex_pk
            server_sig = crypto_sign_detached(server_buf, keys.sk)
            self.kex_sk = kex_sk
            self.handshake = 2
            self.device_key = device_key
        elif self.handshake == 1:
            # parse server data
            if len(self.buffer) < 3+keys.PK_SIZE+keys.KEX_PK_SIZE+keys.SIGN_SIZE:
                return
            server_pk = self.buffer[3:3+keys.PK_SIZE]
            kex_pk = self.buffer[3+keys.PK_SIZE:3+keys.PK_SIZE+keys.KEX_PK_SIZE]
            server_sig = self.buffer[3+keys.PK_SIZE+keys.KEX_PK_SIZE:3+keys.PK_SIZE+keys.KEX_PK_SIZE+keys.SIGN_SIZE]
            signed_buf = self.buffer[:3+keys.PK_SIZE+keys.KEX_PK_SIZE]
            self.buffer = b'' # should have no more data
            try:
                crypto_sign_verify_detached(server_sig, signed_buf, server_pk)
            except:
                self.close_exc = Exception('Invalid signature')
                self.transport.close()
                return
            # then complete
            kex_sk = randombytes(keys.KEX_SK_SIZE)
            client_kex_pk = crypto_scalarmult_curve25519_base(kex_sk)
            signature = crypto_sign_detached(client_kex_pk, keys.sk)
            self.transport.write(client_kex_pk + signature)
            shared_secret = crypto_scalarmult_curve25519(kex_sk, kex_pk)
            key = crypto_sha512(shared_secret)
            self.recv_key = key[:32]
            self.send_key = key[32:]
            self.handshake = 3
            # connected
            self.proto = self.protoFactory()
            self.proto._set_write_function(self.write)
            self.proto.connection_made()
        elif self.handshake == 2:
            # parse client data 2
            if len(self.buffer) < keys.KEX_PK_SIZE + keys.SIGN_SIZE:
                return
            client_kex_pk = self.buffer[:keys.KEX_PK_SIZE]
            signature = self.buffer[keys.KEX_PK_SIZE:keys.KEX_PK_SIZE+keys.SIGN_SIZE]
            try:
                crypto_sign_verify_detached(signature, client_kex_pk, self.device_key)
            except:
                # error verify signature
                self.close_exc = Exception('Invalid signature')
                self.transport.close()
                return
            shared_secret = crypto_scalarmult_curve25519(self.kex_sk, client_kex_pk)
            key = crypto_sha512(shared_secret)
            del self.kex_sk
            self.buffer = self.buffer[keys.KEX_PK_SIZE+keys.SIGN_SIZE:]
            self.send_key = key[:32]
            self.recv_key = key[32:]
            self.handshake = 3
            # connected
            self.proto = self.protoFactory()
            self.proto._set_write_function(self.write)
            self.proto.connection_made()
        else: # self.handshake == 3
            # unpack data, and send to upper object
            while len(self.buffer) >= 4 + keys.TAG_SIZE + keys.NONCE_SIZE:
                length, = struct.unpack('<I', self.buffer[:4])
                if len(self.buffer) < 4 + keys.TAG_SIZE + keys.NONCE_SIZE + length:
                    return
                tag = self.buffer[4:4+keys.TAG_SIZE]
                nonce = self.buffer[4+keys.TAG_SIZE:4+keys.TAG_SIZE+keys.NONCE_SIZE]
                ct = self.buffer[4+keys.TAG_SIZE+keys.NONCE_SIZE:4+keys.TAG_SIZE+keys.NONCE_SIZE+length]
                self.buffer = self.buffer[4+keys.TAG_SIZE+keys.NONCE_SIZE+length:]
                try:
                    # sodium combined mode concats mac after ciphertext
                    msg = crypto_aead_chacha20poly1305_ietf_decrypt(ct + tag, None, nonce, self.recv_key)
                except:
                    # fail to decrypt
                    self.close_exc = Exception('Invalid MAC')
                    self.transport.close()
                    return
                # handle message
                self.proto.message_received(msg)
    def write(data):
        #if self.handshake != 3
        # pack data with AEAD, write data
        length = len(data)
        nonce = randombytes(keys.NONCE_SIZE)
        encrypted = crypto_aead_chacha20poly1305_ietf_encrypt(data, None, nonce, self.send_key)
        ct, tag = encrypted[:length], encrypted[length:]
        lenbuf = struct.pack('<I', length)
        self.transport.write(lenbuf + tag + nonce + ct)

class WPProtocol:
    def _set_write_function(self, write):
        self._write = write
    def connection_made(self):
    def connection_lost(self, exc):
    def message_received(self, message):
    def send_message(self, message):
        self._write(message)
