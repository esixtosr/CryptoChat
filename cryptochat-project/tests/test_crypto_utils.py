import pytest
from cryptography.exceptions import InvalidTag

from crypto_utils import ReplayError, Session, fingerprint_public_key


def make_pair():
    client = Session.create()
    server = Session.create()
    client.set_peer(server.pk, role="client")
    server.set_peer(client.pk, role="server")
    return client, server


def test_client_server_directional_keys_pair_correctly():
    client, server = make_pair()

    assert client.send_key == server.recv_key
    assert client.recv_key == server.send_key
    assert client.send_key != client.recv_key
    assert server.send_key != server.recv_key


def test_encrypt_decrypt_works_in_both_directions():
    client, server = make_pair()

    client_packet = client.encrypt_packet(b"hello from client")
    assert server.decrypt_packet(client_packet) == b"hello from client"

    server_packet = server.encrypt_packet(b"hello from server")
    assert client.decrypt_packet(server_packet) == b"hello from server"


def test_ciphertext_tampering_fails_and_counter_does_not_advance():
    client, server = make_pair()

    packet = client.encrypt_packet(b"authenticated")
    tampered = bytearray(packet)
    tampered[-1] ^= 0x01

    assert server.recv_ctr == 0
    with pytest.raises(InvalidTag):
        server.decrypt_packet(bytes(tampered))
    assert server.recv_ctr == 0

    assert server.decrypt_packet(packet) == b"authenticated"
    assert server.recv_ctr == 1


def test_replayed_messages_fail():
    client, server = make_pair()

    packet = client.encrypt_packet(b"once")
    assert server.decrypt_packet(packet) == b"once"

    with pytest.raises(ReplayError):
        server.decrypt_packet(packet)


def test_unexpected_future_counter_fails_without_advancing():
    client, server = make_pair()

    first = client.encrypt_packet(b"first")
    second = client.encrypt_packet(b"second")

    with pytest.raises(ReplayError):
        server.decrypt_packet(second)
    assert server.recv_ctr == 0

    assert server.decrypt_packet(first) == b"first"
    assert server.recv_ctr == 1


def test_role_pairing_is_symmetric_from_both_sides():
    client, server = make_pair()

    assert client.send_label == server.recv_label
    assert client.recv_label == server.send_label


def test_fingerprint_generation_is_stable_for_same_public_key():
    session = Session.create()

    assert fingerprint_public_key(session.pk) == fingerprint_public_key(session.pk)
    assert session.fingerprint() == fingerprint_public_key(session.pk)
