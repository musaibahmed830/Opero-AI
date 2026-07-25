import time
from unittest.mock import patch

import jwt
import pytest

from app.core.oauth_state import create_state, verify_state


def test_state_round_trips_organization_and_user() -> None:
    state = create_state(organization_id="11111111-1111-1111-1111-111111111111", user_id="auth0|abc123")
    claims = verify_state(state)

    assert claims["organization_id"] == "11111111-1111-1111-1111-111111111111"
    assert claims["user_id"] == "auth0|abc123"


def test_state_rejects_expired_token() -> None:
    with patch("app.core.oauth_state.time") as mock_time:
        mock_time.time.return_value = 1_000_000.0
        state = create_state(organization_id="ws", user_id="user")

    with pytest.raises(jwt.ExpiredSignatureError):
        verify_state(state, max_age_seconds=600)


def test_state_rejects_tampered_token() -> None:
    state = create_state(organization_id="ws", user_id="user")
    tampered = state[:-1] + ("A" if state[-1] != "A" else "B")

    with pytest.raises(jwt.PyJWTError):
        verify_state(tampered)


def test_state_is_still_valid_just_under_the_expiry_window() -> None:
    state = create_state(organization_id="ws", user_id="user")
    with patch("app.core.oauth_state.time") as mock_time:
        mock_time.time.return_value = time.time() + 599
        verify_state(state, max_age_seconds=600)  # should not raise
