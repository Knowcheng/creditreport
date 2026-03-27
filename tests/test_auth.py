import pytest
from backend.core.auth import hash_password, verify_password, create_token, decode_token

def test_password_hash_and_verify():
    hashed = hash_password("mypassword")
    assert hashed != "mypassword"
    assert verify_password("mypassword", hashed) is True
    assert verify_password("wrongpassword", hashed) is False

def test_create_and_decode_token():
    token = create_token(user_id=1, username="testuser", role="user")
    payload = decode_token(token)
    assert payload["user_id"] == 1
    assert payload["username"] == "testuser"
    assert payload["role"] == "user"

def test_decode_invalid_token_raises():
    with pytest.raises(ValueError, match="无效"):
        decode_token("not.a.valid.token")
