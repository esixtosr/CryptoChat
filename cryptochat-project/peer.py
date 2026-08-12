from __future__ import annotations
import json
import socket, threading, struct
from typing import Callable, Optional
from crypto_utils import Session

# Simple framed transport: len(4 bytes BE) | encrypted packet
MAX_MESSAGE_SIZE = 64 * 1024
CONTROL_PREFIX = "\x00cryptochat-control:"
IDENTITY_MESSAGE_TYPE = "identity"

class Peer:
    def __init__(
        self,
        on_message: Callable[[str], None],
        on_status: Callable[[str], None],
        on_identity: Callable[[str], None] | None = None,
        on_peer_address: Callable[[str], None] | None = None,
        local_name: str = "Anonymous",
    ):
        self.on_message = on_message
        self.on_status = on_status
        self.on_identity = on_identity
        self.on_peer_address = on_peer_address
        self.local_name = local_name
        self.sess = Session.create()
        self.sock: Optional[socket.socket] = None
        self._stop = False

    def start_server(self, host='0.0.0.0', port=5556):
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((host, port))
            srv.listen(1)
            self.on_status(f"Listening on {host}:{port} - FP {self.sess.fingerprint()}")
            conn, addr = srv.accept()
            self.sock = conn
            if self.on_peer_address:
                self.on_peer_address(str(addr[0]))
            self.on_status(f"Connected by {addr}")
            # ECDH: server sends pk first, then receives client pk.
            conn.sendall(self.sess.pk)
            peer_pk = self._recv_exact(32)
            if len(peer_pk) != 32:
                raise ConnectionError("handshake failed: missing client public key")
            self.sess.set_peer(peer_pk, role="server")
            self.on_status("Session key established.")
            threading.Thread(target=self._reader, daemon=True).start()
            self._send_identity()
        except Exception as e:
            self.on_status(f"[connection error] {e}")

    def start_client(self, host='127.0.0.1', port=5556):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((host, port))
            self.sock = s
            if self.on_peer_address:
                self.on_peer_address(host)
            self.on_status(f"Connected to {host}:{port} - FP {self.sess.fingerprint()}")
            # ECDH: client receives server pk first, then sends client pk.
            srv_pk = self._recv_exact(32)
            if len(srv_pk) != 32:
                raise ConnectionError("handshake failed: missing server public key")
            s.sendall(self.sess.pk)
            self.sess.set_peer(srv_pk, role="client")
            self.on_status("Session key established.")
            threading.Thread(target=self._reader, daemon=True).start()
            self._send_identity()
        except Exception as e:
            self.on_status(f"[connection error] {e}")

    def _reader(self):
        try:
            while not self._stop:
                try:
                    hdr = self._recv_exact(4)
                except OSError:
                    break
                if not hdr:
                    break
                (ln,) = struct.unpack('>I', hdr)
                if ln <= 0 or ln > MAX_MESSAGE_SIZE:
                    self.on_status(f"[protocol error] invalid frame length: {ln}")
                    break
                try:
                    buf = self._recv_exact(ln)
                except OSError:
                    break
                if len(buf) != ln:
                    self.on_status("[connection error] incomplete frame received")
                    break
                try:
                    msg = self.sess.decrypt_packet(buf).decode('utf-8', 'strict')
                    if not self._handle_control_message(msg):
                        self.on_message(msg)
                except Exception as e:
                    self.on_status(f"[decrypt error] {e}")
                    break
        finally:
            self.close()
            self.on_status("Disconnected.")

    def _recv_exact(self, n: int) -> bytes:
        b = b''
        while len(b) < n:
            if self._stop or not self.sock:
                return b
            chunk = self.sock.recv(n - len(b))
            if not chunk:
                return b
            b += chunk
        return b

    def send(self, text: str):
        if not self.sock:
            raise ConnectionError("no active socket")
        data = text.encode('utf-8')
        if len(data) > MAX_MESSAGE_SIZE:
            raise ValueError(f"message is too large; limit is {MAX_MESSAGE_SIZE} bytes")
        ct = self.sess.encrypt_packet(data)
        if len(ct) > MAX_MESSAGE_SIZE:
            raise ValueError(f"encrypted frame is too large; limit is {MAX_MESSAGE_SIZE} bytes")
        pkt = struct.pack('>I', len(ct)) + ct
        self.sock.sendall(pkt)

    def _send_identity(self):
        identity = {
            "type": IDENTITY_MESSAGE_TYPE,
            "name": self.local_name[:80],
        }
        self.send(CONTROL_PREFIX + json.dumps(identity, separators=(",", ":")))

    def _handle_control_message(self, text: str) -> bool:
        if not text.startswith(CONTROL_PREFIX):
            return False

        try:
            data = json.loads(text[len(CONTROL_PREFIX):])
        except json.JSONDecodeError:
            return False

        if not isinstance(data, dict) or data.get("type") != IDENTITY_MESSAGE_TYPE:
            return False

        name = str(data.get("name", "")).strip()
        if name and self.on_identity:
            self.on_identity(name[:80])
        return True

    def close(self):
        self._stop = True
        sock = self.sock
        self.sock = None
        try:
            if sock:
                sock.shutdown(socket.SHUT_RDWR)
                sock.close()
        except Exception:
            pass
