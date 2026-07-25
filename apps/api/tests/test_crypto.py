from app.core.crypto import decrypt_secret, encrypt_secret


def test_encrypt_decrypt_round_trip() -> None:
    plaintext = "1//0gABCDEF_a_fake_refresh_token"
    ciphertext = encrypt_secret(plaintext)

    assert ciphertext != plaintext
    assert decrypt_secret(ciphertext) == plaintext
