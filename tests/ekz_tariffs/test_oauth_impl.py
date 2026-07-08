from __future__ import annotations

import base64

import aiohttp
import pytest
from custom_components.ekz_tariffs.const import DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN
from custom_components.ekz_tariffs.oauth_impl import EKZOAuth2Implementation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    LocalOAuth2ImplementationWithPkce,
)


def _confidential_impl(hass: HomeAssistant) -> EKZOAuth2Implementation:
    return EKZOAuth2Implementation(
        hass,
        DOMAIN,
        "test-client-id",
        "test-client-secret",
        OAUTH2_AUTHORIZE,
        OAUTH2_TOKEN,
    )


def _public_impl(hass: HomeAssistant) -> EKZOAuth2Implementation:
    return EKZOAuth2Implementation(
        hass, DOMAIN, "test-client-id", "", OAUTH2_AUTHORIZE, OAUTH2_TOKEN
    )


def test_confidential_client_extra_authorize_data_empty(hass: HomeAssistant):
    impl = _confidential_impl(hass)
    assert impl.extra_authorize_data == {}


def test_public_client_extra_authorize_data_has_pkce(hass: HomeAssistant):
    impl = _public_impl(hass)
    data = impl.extra_authorize_data
    assert data["code_challenge_method"] == "S256"
    assert data[
        "code_challenge"
    ] == LocalOAuth2ImplementationWithPkce.compute_code_challenge(
        impl._pkce_code_verifier
    )


@pytest.mark.asyncio
async def test_confidential_token_exchange_sends_basic_header(
    hass: HomeAssistant, aioclient_mock
):
    impl = _confidential_impl(hass)
    aioclient_mock.post(
        OAUTH2_TOKEN, json={"access_token": "at", "refresh_token": "rt"}
    )

    await impl.async_resolve_external_data(
        {"code": "abc", "state": {"redirect_uri": "https://example/callback"}}
    )

    _, _, data, headers = aioclient_mock.mock_calls[-1]
    expected = base64.b64encode(b"test-client-id:test-client-secret").decode()
    assert headers["Authorization"] == f"Basic {expected}"
    assert "client_id" not in data
    assert "code_verifier" not in data


@pytest.mark.asyncio
async def test_public_token_exchange_omits_basic_sends_client_id_and_verifier(
    hass: HomeAssistant, aioclient_mock
):
    impl = _public_impl(hass)
    aioclient_mock.post(
        OAUTH2_TOKEN, json={"access_token": "at", "refresh_token": "rt"}
    )

    await impl.async_resolve_external_data(
        {"code": "abc", "state": {"redirect_uri": "https://example/callback"}}
    )

    _, _, data, headers = aioclient_mock.mock_calls[-1]
    assert "Authorization" not in headers
    assert data["client_id"] == "test-client-id"
    assert data["code_verifier"] == impl._pkce_code_verifier


@pytest.mark.asyncio
async def test_confidential_refresh_sends_basic_header_no_client_id(
    hass: HomeAssistant, aioclient_mock
):
    impl = _confidential_impl(hass)
    aioclient_mock.post(OAUTH2_TOKEN, json={"access_token": "new-at"})

    await impl._async_refresh_token({"refresh_token": "rt-1", "access_token": "old"})

    _, _, data, headers = aioclient_mock.mock_calls[-1]
    expected = base64.b64encode(b"test-client-id:test-client-secret").decode()
    assert headers["Authorization"] == f"Basic {expected}"
    assert "client_id" not in data
    assert "code_verifier" not in data


@pytest.mark.asyncio
async def test_public_refresh_omits_basic_sends_client_id_no_verifier(
    hass: HomeAssistant, aioclient_mock
):
    impl = _public_impl(hass)
    aioclient_mock.post(OAUTH2_TOKEN, json={"access_token": "new-at"})

    await impl._async_refresh_token({"refresh_token": "rt-1", "access_token": "old"})

    _, _, data, headers = aioclient_mock.mock_calls[-1]
    assert "Authorization" not in headers
    assert data["client_id"] == "test-client-id"
    assert "code_verifier" not in data


@pytest.mark.asyncio
async def test_token_exchange_error_status_logs_and_raises(
    hass: HomeAssistant, aioclient_mock
):
    impl = _confidential_impl(hass)
    aioclient_mock.post(OAUTH2_TOKEN, status=401, json={"error": "invalid_client"})

    with pytest.raises(aiohttp.ClientResponseError):
        await impl.async_resolve_external_data(
            {"code": "abc", "state": {"redirect_uri": "https://example/callback"}}
        )
