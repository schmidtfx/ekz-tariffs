"""Custom OAuth2 implementation for EKZ."""

from __future__ import annotations

import base64
import logging
from typing import Any

import aiohttp
from homeassistant.helpers import config_entry_oauth2_flow

_LOGGER = logging.getLogger(__name__)


class EKZOAuth2Implementation(config_entry_oauth2_flow.LocalOAuth2Implementation):
    """Custom OAuth2 implementation for EKZ with Basic authentication."""

    def _encode_credentials(self) -> str:
        """Encode client credentials as Base64 for HTTP Basic auth."""
        credentials = f"{self.client_id}:{self.client_secret}"
        return base64.b64encode(credentials.encode()).decode()

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Resolve external data to tokens, using HTTP Basic auth for client credentials."""
        # EKZ requires client credentials to be sent via HTTP Basic authentication
        # NOT in the request body as client_id/client_secret
        headers = {
            "Authorization": f"Basic {self._encode_credentials()}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {
            "grant_type": "authorization_code",
            "code": external_data["code"],
            "redirect_uri": external_data["state"]["redirect_uri"],
        }

        async with (
            aiohttp.ClientSession() as session,
            session.post(
                self.token_url,
                headers=headers,
                data=data,
            ) as resp,
        ):
            if resp.status != 200:
                error_text = await resp.text()
                _LOGGER.error(
                    "Token request failed with %s: %s",
                    resp.status,
                    error_text,
                )
            resp.raise_for_status()
            return await resp.json()

    async def _async_refresh_token(self, token: dict) -> dict:
        """Refresh tokens, using HTTP Basic auth for client credentials."""
        headers = {
            "Authorization": f"Basic {self._encode_credentials()}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {
            "grant_type": "refresh_token",
            "refresh_token": token["refresh_token"],
        }

        async with (
            aiohttp.ClientSession() as session,
            session.post(
                self.token_url,
                headers=headers,
                data=data,
            ) as resp,
        ):
            resp.raise_for_status()
            new_token = await resp.json()
            return {**token, **new_token}
