import pytest
from backend.auth import hash_password, verify_password, generate_api_key


def test_hash_password():
    password = "test_password_123"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong_password", hashed)


def test_generate_api_key():
    plain, hashed, prefix = generate_api_key()
    assert plain.startswith("mk_")
    assert len(prefix) == 8
    assert len(hashed) == 64
