#!/usr/bin/env python3

import asyncio
from crypto import *
import keys
import struct

READ_BUFFER_HIGH_WATER_MARK = 16

# 0 - init
# 1 - client handshake
# 2 - server handshake
# 3 - client complete
class TCPProtocol(asyncio.Protocol):
    def __init__(self, wpproto_factory, is_server = False):
        self.is_server = is_server
        self.wpproto = wpproto_factory()
        self.close_exc = None
        self.send_nonce = Nonce(keys.NONCE_SIZE)
        self.recv_nonce = Nonce(keys.NONCE_SIZE)
    def connection_made(self, transport):
        self.transport = transport
        self._paused = False
        self.buffer = b''
        if self.is_server:
            self.handshake = 0
        else:
            # client launch handshake
            challenge = randombytes(32)
            handshake_buf = b'\x01\x03\x02\x43\x82\x43' + keys.pk + challenge
            signature = crypto_sign_detached(handshake_buf, keys.sk)
            self.transport.write(handshake_buf + signature)
            self.handshake = 1
            self.challenge = challenge
        self.wpproto._set_proto(self)
    def connection_lost(self, exc):
        if exc == None:
            exc = self.close_exc
        if self.handshake == 3:
            self.wpproto.connection_lost(exc)
        else:
            self.wpproto.handshake_failed(exc)
    def data_received(self, data):
        self.buffer = self.buffer + data
        if self.handshake == 0:
            # parse client data
            if len(self.buffer) < 6 + keys.PK_SIZE + keys.SIGN_SIZE: # TODO: check the content of the header, calculate the correct length
                return
            device_key = self.buffer[6:6 + keys.PK_SIZE]
            client_challenge = self.buffer[6 + keys.PK_SIZE:6 + keys.PK_SIZE + 32]
            signature = self.buffer[6 + keys.PK_SIZE + 32:6 + keys.PK_SIZE + 32 + keys.SIGN_SIZE]
            handshake_buf = self.buffer[:6 + keys.PK_SIZE + 32]
            try:
                crypto_sign_verify_detached(signature, handshake_buf, device_key)
            except:
                # error verify signature
                self.close_exc = NetworkCryptoException('Invalid signature')
                self.transport.close()
                return
            #self.buffer = self.buffer[6 + keys.PK_SIZE + keys.SIGN_SIZE:]
            self.buffer = b'' # should have no more data
            kex_sk = randombytes(keys.KEX_SK_SIZE)
            kex_pk = crypto_scalarmult_curve25519_base(kex_sk)
            challenge = randombytes(32)
            server_buf = b'\x43\x02\x82' + keys.pk + kex_pk + challenge
            server_sig = crypto_sign_detached(server_buf + client_challenge, keys.sk)
            self.transport.write(server_buf + server_sig)
            self.kex_sk = kex_sk
            self.challenge = challenge
            self.handshake = 2
            self._peer_key = device_key
        elif self.handshake == 1:
            # parse server data
            if len(self.buffer) < 3+keys.PK_SIZE+keys.KEX_PK_SIZE+keys.SIGN_SIZE:
                return
            server_pk = self.buffer[3:3+keys.PK_SIZE]
            kex_pk = self.buffer[3+keys.PK_SIZE:3+keys.PK_SIZE+keys.KEX_PK_SIZE]
            server_challenge = self.buffer[3+keys.PK_SIZE+keys.KEX_PK_SIZE:3+keys.PK_SIZE+keys.KEX_PK_SIZE+32]
            server_sig = self.buffer[3+keys.PK_SIZE+keys.KEX_PK_SIZE+32:3+keys.PK_SIZE+keys.KEX_PK_SIZE+32+keys.SIGN_SIZE]
            signed_buf = self.buffer[:3+keys.PK_SIZE+keys.KEX_PK_SIZE+32]
            self.buffer = b'' # should have no more data
            try:
                crypto_sign_verify_detached(server_sig, signed_buf + self.challenge, server_pk)
            except:
                self.close_exc = NetworkCryptoException('Invalid signature')
                self.transport.close()
                return
            # then complete
            kex_sk = randombytes(keys.KEX_SK_SIZE)
            client_kex_pk = crypto_scalarmult_curve25519_base(kex_sk)
            signature = crypto_sign_detached(client_kex_pk + server_challenge, keys.sk)
            self.transport.write(client_kex_pk + signature)
            shared_secret = crypto_scalarmult_curve25519(kex_sk, kex_pk)
            key = crypto_hash_sha512(shared_secret)
            del self.challenge
            self.recv_key = key[:32]
            self.send_key = key[32:]
            self.handshake = 3
            self._peer_key = server_pk
            # connected
            self.wpproto.connection_made()
        elif self.handshake == 2:
            # parse client data 2
            if len(self.buffer) < keys.KEX_PK_SIZE + keys.SIGN_SIZE:
                return
            client_kex_pk = self.buffer[:keys.KEX_PK_SIZE]
            signature = self.buffer[keys.KEX_PK_SIZE:keys.KEX_PK_SIZE+keys.SIGN_SIZE]
            try:
                crypto_sign_verify_detached(signature, client_kex_pk + self.challenge, self._peer_key)
            except:
                # error verify signature
                self.close_exc = NetworkCryptoException('Invalid signature')
                self.transport.close()
                return
            shared_secret = crypto_scalarmult_curve25519(self.kex_sk, client_kex_pk)
            key = crypto_hash_sha512(shared_secret)
            del self.kex_sk
            del self.challenge
            self.buffer = self.buffer[keys.KEX_PK_SIZE+keys.SIGN_SIZE:]
            self.send_key = key[:32]
            self.recv_key = key[32:]
            self.handshake = 3
            # connected
            self.wpproto.connection_made()
        # may have remain data after handshake
        if self.handshake == 3:
            # unpack data, and send to upper object
            while len(self.buffer) >= 4 + keys.TAG_SIZE:
                length, = struct.unpack('<I', self.buffer[:4])
                if len(self.buffer) < 4 + keys.TAG_SIZE + length:
                    return
                tag = self.buffer[4:4+keys.TAG_SIZE]
                nonce = self.recv_nonce.get()
                ct = self.buffer[4+keys.TAG_SIZE:4+keys.TAG_SIZE+length]
                self.buffer = self.buffer[4+keys.TAG_SIZE+length:]
                try:
                    # sodium combined mode concats mac after ciphertext
                    msg = crypto_aead_chacha20poly1305_ietf_decrypt(ct + tag, b'', nonce, self.recv_key)
                except:
                    # fail to decrypt
                    self.close_exc = NetworkCryptoException('Invalid MAC')
                    self.transport.close()
                    return
                # handle message
                self.wpproto.message_received(msg)
    def pause_writing():
        self.wpproto.pause_writing()
    def resume_writing():
        self.wpproto.resume_writing()
    def write(self, data):
        if self.handshake != 3:
            raise NetworkStateException('handshake not completed')
        # pack data with AEAD, write data
        length = len(data)
        nonce = self.send_nonce.get()
        encrypted = crypto_aead_chacha20poly1305_ietf_encrypt(data, b'', nonce, self.send_key)
        ct, tag = encrypted[:length], encrypted[length:]
        lenbuf = struct.pack('<I', length)
        self.transport.write(lenbuf + tag + ct)
    def close(self):
        self.transport.close()
    def peer_key(self):
        return self._peer_key
    def pause(self):
        if not self._paused:
            self.transport.pause_reading()
            self._paused = True
    def resume(self):
        if self._paused:
            self.transport.resume_reading()
            self._paused = False

class WPProtocol:
    # internal functions
    def _set_proto(self, tcpproto):
        self.tcpproto = tcpproto
    # exported interfaces
    def send_message(self, message):
        self.tcpproto.write(message)
    def peer_key(self):
        return self.tcpproto.peer_key()
    def close(self):
        self.tcpproto.close()
    def pause(self):
        self.tcpproto.pause()
    def resume(self):
        self.tcpproto.resume()
    def drain(self):
        result = asyncio.Future()
        if not hasattr(self, '_drained'):
            self._drained = True
        if self._drained:
            result.set_result(None)
        else:
            if not hasattr(self, '_drainfuture'):
                self._drainfuture = []
            self._drainfuture.append(result)
        return result
    # default implemented flow control
    def pause_writing(self):
        self._drained = False
    def resume_writing(self):
        self._drained = True
        if hasattr(self, '_drainfuture'):
            for f in self._drainfuture:
                f.set_result(None)
        self._drainfuture = []
    # overriden functions
    def handshake_failed(self, exc):
        pass
    def connection_made(self):
        pass
    def connection_lost(self, exc):
        pass
    def message_received(self, message):
        pass

class WPStreamProtocol(WPProtocol):
    def __init__(self, stream_future):
        self.stream_future = stream_future
    def handshake_failed(self, exc):
        self.stream_future.set_exception(exc)
    def connection_made(self):
        stream = WPStream(self)
        self.stream_future.set_result(stream)
        self.stream = stream
    def connection_lost(self, exc):
        self.stream._close(exc)
    def message_received(self, message):
        self.stream._push(message)

class WPListenerProtocol(WPProtocol):
    def __init__(self, conn_handler):
        self.conn_handler = conn_handler
    def handshake_failed(self, exc):
        pass
    def connection_made(self):
        stream = WPStream(self)
        self.stream = stream
        self.conn_handler(stream)
    def connection_lost(self, exc):
        self.stream._close(exc)
    def message_received(self, message):
        self.stream._push(message)

class WPStream:
    def __init__(self, wpproto):
        self.wpproto = wpproto
        self.readbuffer = []
        self.readfuture = []
        self.readable = True
        self.writable = True
        self.exc = None
    def _push(self, data):
        if len(self.readfuture) > 0:
            future = self.readfuture[0]
            del self.readfuture[0]
            future.set_result(data)
        else:
            self.readbuffer.append(data)
            if len(self.readbuffer) >= READ_BUFFER_HIGH_WATER_MARK:
                self.wpproto.pause()
    def _close(self, exc):
        self.readable = False
        self.writable = False
        self.exc = exc
        for future in self.readfuture:
            future.set_exception(NetworkClosedException() if exc == None else exc)
    def read(self):
        result = asyncio.Future()
        if len(self.readbuffer) > 0:
            result.set_result(self.readbuffer[0])
            del self.readbuffer[0]
            if len(self.readbuffer) < READ_BUFFER_HIGH_WATER_MARK:
                self.wpproto.resume()
        else:
            if self.readable:
                self.readfuture.append(result)
                self.wpproto.resume()
            else:
                result.set_exception(NetworkClosedException())
        return asyncio.ensure_future(result)
    def close(self):
        self.writable = False
        self.wpproto.close()
    def write(self, msg):
        if not self.writable:
            raise NetworkClosedException()
        self.wpproto.send_message(msg)
    async def drain(self):
        await self.wpproto.drain()
    def peer_key(self):
        return self.wpproto.peer_key()
    def can_read(self):
        return readable
    def can_write(self):
        return writable
    def get_exception(self):
        return self.exc

class NetworkException(Exception):
    pass
class NetworkCryptoException(NetworkException):
    pass
class NetworkClosedException(NetworkException):
    pass
class NetworkStateException(NetworkException):
    pass

async def connect(addr):
    loop = asyncio.get_event_loop()
    stream_future = asyncio.Future()
    await loop.create_connection(
        lambda: TCPProtocol(lambda: WPStreamProtocol(stream_future)), addr[0], addr[1])
    return await stream_future

async def listen(addr, conn_handler):
    loop = asyncio.get_event_loop()
    server = await loop.create_server(
        lambda: TCPProtocol(lambda: WPListenerProtocol(conn_handler), is_server=True), addr[0], addr[1])
    return server
