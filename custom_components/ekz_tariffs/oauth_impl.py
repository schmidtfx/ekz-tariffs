"""Custom OAuth2 implementation for EKZ."""

from __future__ import annotations

import base64
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)


class EKZOAuth2Implementation(config_entry_oauth2_flow.LocalOAuth2Implementation):
    """Custom OAuth2 implementation for EKZ.

    Supports both confidential clients (client_id + client_secret, sent via
    HTTP Basic auth) and public clients (client_id only, using PKCE). The
    client type is auto-detected from whether a client_secret is present.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        domain: str,
        client_id: str,
        client_secret: str,
        authorize_url: str,
        token_url: str,
    ) -> None:
        """Initialize, detecting confidential vs. public client type."""
        super().__init__(
            hass, domain, client_id, client_secret, authorize_url, token_url
        )
        self._is_public_client = not client_secret
        self._pkce_code_verifier = (
            config_entry_oauth2_flow.LocalOAuth2ImplementationWithPkce.generate_code_verifier()
            if self._is_public_client
            else None
        )

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        if not self._is_public_client:
            return {}
        return {
            "code_challenge": config_entry_oauth2_flow.LocalOAuth2ImplementationWithPkce.compute_code_challenge(
                self._pkce_code_verifier
            ),
            "code_challenge_method": "S256",
        }

    def _encode_credentials(self) -> str:
        """Encode client credentials as Base64 for HTTP Basic auth."""
        credentials = f"{self.client_id}:{self.client_secret}"
        return base64.b64encode(credentials.encode()).decode()

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Resolve external data to tokens.

        Confidential clients authenticate via HTTP Basic auth (EKZ requires
        this NOT in the request body). Public clients have no client_secret
        and instead authenticate via PKCE, sending client_id and
        code_verifier in the body.
        """
        data = {
            "grant_type": "authorization_code",
            "code": external_data["code"],
            "redirect_uri": external_data["state"]["redirect_uri"],
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        if self._is_public_client:
            data["client_id"] = self.client_id
            data["code_verifier"] = self._pkce_code_verifier
        else:
            headers["Authorization"] = f"Basic {self._encode_credentials()}"

        return await self._async_token_request(data, headers)

    async def _async_refresh_token(self, token: dict) -> dict:
        """Refresh tokens, using HTTP Basic auth or PKCE depending on client type."""
        data = {
            "grant_type": "refresh_token",
            "refresh_token": token["refresh_token"],
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        if self._is_public_client:
            data["client_id"] = self.client_id
        else:
            headers["Authorization"] = f"Basic {self._encode_credentials()}"

        new_token = await self._async_token_request(data, headers)
        return {**token, **new_token}

    async def _async_token_request(
        self, data: dict[str, str], headers: dict[str, str]
    ) -> dict:
        """POST a token request and return the decoded JSON response."""
        session = async_get_clientsession(self.hass)
        resp = await session.post(self.token_url, headers=headers, data=data)
        if resp.status != 200:
            error_text = await resp.text()
            _LOGGER.error(
                "Token request failed with %s: %s",
                resp.status,
                error_text,
            )
        resp.raise_for_status()
        return await resp.json()
