#!/usr/bin/env python3

from pysodium import *
import json
import base64

# we use ed25519 keys

pk = None
sk = None

try:
    with open('keys.json', 'r') as f:
        keypair = json.loads(f.read())
        pk = base64.b64decode(keypair['pk'])
        sk = base64.b64decode(keypair['sk'])
except FileNotFoundError:
    pk, sk = crypto_sign_keypair()
    with open('keys.json', 'w') as f:
        f.write(json.dumps({
            'pk': base64.b64encode(pk).decode(),
            'sk': base64.b64encode(sk).decode(),
            'type': 'ed25519'
        }))

PK_SIZE = crypto_sign_ed25519_PUBLICKEYBYTES
SK_SIZE = crypto_sign_ed25519_SECRETKEYBYTES
SIGN_SIZE = crypto_sign_BYTES

KEY_SIZE = crypto_aead_chacha20poly1305_ietf_KEYBYTES
NONCE_SIZE = crypto_aead_chacha20poly1305_ietf_NONCEBYTES
TAG_SIZE = crypto_aead_chacha20poly1305_ABYTES

KEX_SK_SIZE = crypto_scalarmult_curve25519_BYTES
KEX_PK_SIZE = crypto_scalarmult_curve25519_BYTES
