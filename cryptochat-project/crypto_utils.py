from __future__ import annotations
from dataclasses import dataclass
import struct
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


PROTOCOL_NAME = b"CryptoChat-v1"
HKDF_INFO = PROTOCOL_NAME + b"|X25519|AES-256-GCM|directional-keys"
CLIENT_TO_SERVER = b"client-to-server"
SERVER_TO_CLIENT = b"server-to-client"


class SessionError(Exception):
    """Base class for session-level protocol failures."""


class SessionNotReady(SessionError):
    """Raised when encryption/decryption is attempted before the handshake."""


class ReplayError(SessionError):
    """Raised when a packet counter is duplicate, old, or out of order."""


def fingerprint_public_key(public_key: bytes) -> str:
    """Return a stable 16-byte truncated SHA-256 fingerprint for a public key."""
    h = hashes.Hash(hashes.SHA256())
    h.update(public_key)
    fp = h.finalize()[:16]
    return ':'.join(f'{b:02x}' for b in fp)


@dataclass
class Session:
    sk: X25519PrivateKey
    pk: bytes
    peer_pk: bytes | None = None
    role: str | None = None
    send_key: bytes | None = None
    recv_key: bytes | None = None
    send_label: bytes | None = None
    recv_label: bytes | None = None
    send_ctr: int = 0
    recv_ctr: int = 0

    @staticmethod
    def create() -> 'Session':
        sk = X25519PrivateKey.generate()
        pk = sk.public_key().public_bytes_raw()
        return Session(sk=sk, pk=pk)

    def set_peer(self, peer_pk: bytes, role: str):
        if role not in {"client", "server"}:
            raise ValueError("role must be 'client' or 'server'")

        self.peer_pk = peer_pk
        self.role = role
        peer = X25519PublicKey.from_public_bytes(peer_pk)
        shared = self.sk.exchange(peer)
        key_material = HKDF(
            algorithm=hashes.SHA256(), length=64, salt=None, info=HKDF_INFO
        ).derive(shared)
        client_to_server_key = key_material[:32]
        server_to_client_key = key_material[32:]

        if role == "client":
            self.send_key = client_to_server_key
            self.recv_key = server_to_client_key
            self.send_label = CLIENT_TO_SERVER
            self.recv_label = SERVER_TO_CLIENT
        else:
            self.send_key = server_to_client_key
            self.recv_key = client_to_server_key
            self.send_label = SERVER_TO_CLIENT
            self.recv_label = CLIENT_TO_SERVER

    def _nonce(self, ctr: int) -> bytes:
        # 96-bit nonce from counter
        return ctr.to_bytes(12, 'big')

    def _aad(self, direction: bytes, ctr: int) -> bytes:
        return b"|".join([PROTOCOL_NAME, b"message", direction, struct.pack(">Q", ctr)])

    def encrypt_packet(self, plaintext: bytes) -> bytes:
        if self.send_key is None or self.send_label is None:
            raise SessionNotReady("session keys are not established")

        aes = AESGCM(self.send_key)
        nonce = self._nonce(self.send_ctr)
        aad = self._aad(self.send_label, self.send_ctr)
        ciphertext = aes.encrypt(nonce, plaintext, aad)
        packet = struct.pack(">Q", self.send_ctr) + ciphertext
        self.send_ctr += 1
        return packet

    def decrypt_packet(self, packet: bytes) -> bytes:
        if self.recv_key is None or self.recv_label is None:
            raise SessionNotReady("session keys are not established")
        if len(packet) < 8 + 16:
            raise ValueError("encrypted packet is too short")

        (ctr,) = struct.unpack(">Q", packet[:8])
        if ctr != self.recv_ctr:
            raise ReplayError(f"unexpected message counter {ctr}; expected {self.recv_ctr}")

        aes = AESGCM(self.recv_key)
        nonce = self._nonce(ctr)
        aad = self._aad(self.recv_label, ctr)
        plaintext = aes.decrypt(nonce, packet[8:], aad)
        self.recv_ctr += 1
        return plaintext

    def encrypt(self, plaintext: bytes, aad: bytes | None = None) -> bytes:
        """Backward-compatible wrapper. Prefer encrypt_packet for new code."""
        if aad is not None:
            raise ValueError("custom AAD is not supported by CryptoChat packets")
        return self.encrypt_packet(plaintext)

    def decrypt(self, ciphertext: bytes, aad: bytes | None = None) -> bytes:
        """Backward-compatible wrapper. Prefer decrypt_packet for new code."""
        if aad is not None:
            raise ValueError("custom AAD is not supported by CryptoChat packets")
        return self.decrypt_packet(ciphertext)

    def fingerprint(self) -> str:
        """Local public key fingerprint (16-byte truncated SHA256)."""
        return fingerprint_public_key(self.pk)

    def peer_fingerprint(self) -> str:
        """Remote public key fingerprint (16-byte truncated SHA256)."""
        if not self.peer_pk:
            return "-"
        return fingerprint_public_key(self.peer_pk)
