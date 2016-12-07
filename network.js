const co = require('co');
const net = require('net');
const sodium = require('sodium').api;
const crypto = require('crypto');
const chacha = require('chacha');
const fs = require('fs');

const randomBytes = crypto.randomBytes;

let keys = {
    PK_SIZE: sodium.crypto_sign_ed25519_PUBLICKEYBYTES,
    SK_SIZE: sodium.crypto_sign_ed25519_SECRETKEYBYTES,
    SIGN_SIZE: sodium.crypto_sign_BYTES,
    KEY_SIZE: sodium.crypto_aead_chacha20poly1305_ietf_KEYBYTES,
    NONCE_SIZE: sodium.crypto_aead_chacha20poly1305_ietf_NPUBBYTES,
    TAG_SIZE: sodium.crypto_aead_chacha20poly1305_ietf_ABYTES,
    KEX_SK_SIZE: sodium.crypto_scalarmult_curve25519_BYTES,
    KEX_PK_SIZE: sodium.crypto_scalarmult_curve25519_BYTES,
};

try {
    let k = JSON.parse(fs.readFileSync('keys.json').toString());
    keys.pk = new Buffer(k.pk, 'base64');
    keys.sk = new Buffer(k.sk, 'base64');
    keys.type = k.type;
} catch (e) {
    let kp = sodium.crypto_sign_ed25519_keypair();
    let k = {
        pk: kp.publicKey.toString('base64'),
        sk: kp.secretKey.toString('base64'),
        type: 'ed25519'
    }
    fs.writeFileSync('keys.json', JSON.stringify(k));
    keys.pk = kp.publicKey;
    keys.sk = kp.secretKey;
    keys.type = 'ed25519';
}

function Nonce(size) {
    this.nonce = new Buffer(size);
    this.nonce.fill(0);
}
Nonce.prototype.get = function () {
    let result = new Buffer(this.nonce.length);
    this.nonce.copy(result);
    for (let i = 0; i < this.nonce.length; i++) {
        this.nonce[i]++;
        if (this.nonce[i] !== 0) {
            break;
        }
    }
    return result;
}

let connect = co.wrap(function *(host, port) {
    let stream = new Stream(host, port);
    let challenge = randomBytes(32);
    let handshake_buf = Buffer.concat([
        new Buffer('\x01\x03\x02\x43\x82\x43', 'binary'),
        keys.pk,
        challenge
    ]);
    let signature = sodium.crypto_sign_detached(handshake_buf, keys.sk)
    stream.stream.write(handshake_buf);
    stream.stream.write(signature);

    let header = yield stream.readbuf(3);
    let server_pk = yield stream.readbuf(keys.PK_SIZE);
    let server_kex = yield stream.readbuf(keys.KEX_PK_SIZE);
    let server_challenge = yield stream.readbuf(32);
    let server_sig = yield stream.readbuf(keys.SIGN_SIZE);
    let check_buf = Buffer.concat([header, server_pk, server_kex, server_challenge, challenge]);

    if (!sodium.crypto_sign_verify_detached(server_sig, check_buf, server_pk)) {
        throw new Error('invalid signature');
    }

    let kex_sk = randomBytes(keys.KEX_SK_SIZE);
    let kex_pk = sodium.crypto_scalarmult_curve25519_base(kex_sk);
    let signature2 = sodium.crypto_sign_detached(Buffer.concat([kex_pk, server_challenge]), keys.sk);
    stream.stream.write(kex_pk);
    stream.stream.write(signature2);
    let shared_secret = sodium.crypto_scalarmult_curve25519(kex_sk, server_kex);
    let keypair = sodium.crypto_hash_sha512(shared_secret);
    stream.recv_key = keypair.slice(0, 32);
    stream.send_key = keypair.slice(32);
    // handshake finished here

    return stream;
})

function Stream(host, port) {
    this.stream = net.connect(port, host);
    this.readpromise = []
    this.bufdata = new Buffer(0);
    this.send_nonce = new Nonce(keys.NONCE_SIZE); // CHACHA20 Nonce Size = 12!
    this.recv_nonce = new Nonce(keys.NONCE_SIZE);
    this.stream.on('data', (buf) => {
        this.bufdata = Buffer.concat([this.bufdata, buf]);
        this.handlebuf();
    });
    this.stream.on('error', (e) => this.exc = e);
    this.stream.on('close', () => {
        for (let p of this.readpromise) {
            p.reject(new Error('connection closed'));
        }
    });
}
Stream.prototype.readbuf = function (size) {
    let prom = new Promise((resolve, reject) => {
        this.readpromise.push({resolve, reject, size});
    });
    this.handlebuf();
    return prom;
}
Stream.prototype.handlebuf = function () {
    while (this.readpromise.length > 0 && this.bufdata.length >= this.readpromise[0].size) {
        let prom = this.readpromise.splice(0, 1)[0];
        prom.resolve(this.bufdata.slice(0, prom.size));
        this.bufdata = this.bufdata.slice(prom.size);
    }
}

Stream.prototype.write = function (buf) {
    let len = new Buffer(2);
    len.writeUInt16LE(buf.length, 0);
    let cipher = chacha.createCipher(this.send_key, this.send_nonce.get());
    let encbuf = cipher.update(buf);
    cipher.final();
    let tag = cipher.getAuthTag();
    this.stream.write(Buffer.concat([len, tag, encbuf]));
}
Stream.prototype.sendjson = function () {}
Stream.prototype.sendfile = function () {}

Stream.prototype.read = co.wrap(function *() {
    let len = (yield this.readbuf(2)).readUInt16LE(0);
    let tag = yield this.readbuf(keys.TAG_SIZE); // POLY1305 Tag Size = 16!
    let ct = yield this.readbuf(len);
    let decipher = chacha.createDecipher(this.recv_key, this.recv_nonce.get());
    decipher.setAuthTag(tag);
    let data = decipher.update(ct);
    decipher.final();
    return data;
})
Stream.prototype.readjson = function () {}
Stream.prototype.readfile = function () {}

Stream.prototype.end = function () {
    this.stream.end();
}

// test
/*
co(function *() {
    let stream = yield connect('127.0.0.1', 22345);
    stream.write(new Buffer('hello, world'));
    console.log((yield stream.read()).toString());
    stream.write(new Buffer('hello, world'));
    console.log((yield stream.read()).toString());
    stream.write(new Buffer('hello, world'));
    stream.write(new Buffer('hello, world'));
    stream.write(new Buffer('hello, world'));
    console.log((yield stream.read()).toString());
    console.log((yield stream.read()).toString());
    console.log((yield stream.read()).toString());
    stream.end();
})
*/

module.exports = { connect, keys };
