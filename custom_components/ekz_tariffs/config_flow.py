from __future__ import annotations

import logging
import uuid
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EkzTariffsOAuthApi
from .const import (
    AUTH_TYPE_OAUTH,
    AUTH_TYPE_PUBLIC,
    CONF_AUTH_TYPE,
    CONF_EMS_INSTANCE_ID,
    CONF_TARIFF_NAME,
    DEFAULT_TARIFF_NAME,
    DOMAIN,
    OAUTH2_SCOPES,
)

_LOGGER = logging.getLogger(__name__)

TARIFF_CHOICES = ["400D", "400F", "400ST", "400WP", "400L", "400LS", "16L", "16LS"]


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle EKZ OAuth2 authentication."""

    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return _LOGGER

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": " ".join(OAUTH2_SCOPES),
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user - choose authentication type."""
        return await self.async_step_auth_type(user_input)

    async def async_step_auth_type(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle authentication type selection."""
        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Required(CONF_AUTH_TYPE, default=AUTH_TYPE_PUBLIC): vol.In(
                        {
                            AUTH_TYPE_PUBLIC: "Public API (select tariff manually)",
                            AUTH_TYPE_OAUTH: "Customer Account (OAuth - personalized tariffs)",
                        }
                    ),
                }
            )
            return self.async_show_form(step_id="auth_type", data_schema=schema)

        auth_type = user_input[CONF_AUTH_TYPE]

        if auth_type == AUTH_TYPE_PUBLIC:
            return await self.async_step_public_config()
        else:
            return await self.async_step_pick_implementation()

    async def async_step_public_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle public API configuration."""
        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Required(CONF_TARIFF_NAME, default=DEFAULT_TARIFF_NAME): vol.In(
                        TARIFF_CHOICES
                    ),
                }
            )
            return self.async_show_form(step_id="public_config", data_schema=schema)

        await self.async_set_unique_id(
            f"{DOMAIN}_public_{user_input[CONF_TARIFF_NAME]}"
        )
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"EKZ {user_input[CONF_TARIFF_NAME]}",
            data={
                CONF_AUTH_TYPE: AUTH_TYPE_PUBLIC,
                CONF_TARIFF_NAME: user_input[CONF_TARIFF_NAME],
            },
        )

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> FlowResult:
        """Create an entry for OAuth flow - check EMS linking first."""
        # Generate unique EMS instance ID for this Home Assistant instance
        ems_instance_id = str(uuid.uuid4())

        # Store the data temporarily for the linking check
        self.oauth_data = data
        self.ems_instance_id = ems_instance_id

        # Show form to complete EMS linking
        return await self.async_step_ems_linking()

    async def async_step_ems_linking(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle EMS linking process by calling the EKZ API."""
        if user_input is None:
            try:
                # Create temporary OAuth session with the token we just got
                session = async_get_clientsession(self.hass)

                # Create a minimal OAuth session-like object
                class TempOAuthSession:
                    def __init__(self, token):
                        self.token = token

                    async def async_ensure_token_valid(self):
                        pass

                temp_session = TempOAuthSession(self.oauth_data["token"])
                api = EkzTariffsOAuthApi(temp_session, session)

                # Build redirect URI using my.home-assistant.io
                # When EKZ finishes linking, it will redirect here, which will route back to HA
                redirect_uri = (
                    f"https://my.home-assistant.io/redirect/ekz-ems-linking?"
                    f"domain={DOMAIN}&flow_id={self.flow_id}"
                )

                # Call the EMS link status API with the OAuth token
                # This API uses the token to identify the user and returns the linking URL if needed
                link_status_response = await api.check_ems_link_status(
                    self.ems_instance_id, redirect_uri
                )

                _LOGGER.info("EMS link status response: %s", link_status_response)

                # Check for error response
                if link_status_response.get("error"):
                    _LOGGER.warning(
                        "EMS link status check returned error %s: %s",
                        link_status_response.get("status"),
                        link_status_response.get("message"),
                    )
                    # Proceed anyway - the integration will handle linking later
                    return await self.async_step_ems_linking_complete()

                # Check if linking is required
                if link_status_response.get("link_status") == "link_required":
                    linking_url = link_status_response.get(
                        "linking_process_redirect_uri"
                    )

                    if linking_url:
                        _LOGGER.info(
                            "EMS linking required, showing manual linking form"
                        )

                        # Store the linking URL for the form
                        self.linking_url = linking_url

                        # Truncate URL for display (show first 50 chars + ...)
                        # But keep full URL for the actual link
                        truncated_url = (
                            linking_url[:50] + "..."
                            if len(linking_url) > 50
                            else linking_url
                        )

                        # Show a form with the linking URL and instructions
                        # User will manually open the URL, complete linking, and click Submit
                        return self.async_show_form(
                            step_id="ems_linking",
                            data_schema=vol.Schema({}),
                            description_placeholders={
                                "linking_url": linking_url,
                                "truncated_url": truncated_url,
                            },
                        )

                # If already linked or no linking required, proceed
                _LOGGER.info("EMS already linked or linking not required")
                return await self.async_step_ems_linking_complete()

            except Exception as err:
                _LOGGER.error("Error checking EMS link status: %s", err, exc_info=True)
                # If we can't check, just proceed and let the integration handle it
                return await self.async_step_ems_linking_complete()

        # User clicked "Next" after completing the linking on EKZ portal
        _LOGGER.info(
            "User confirmed EMS linking completion, proceeding to finalize setup"
        )
        return await self.async_step_ems_linking_complete()

    async def async_step_ems_linking_complete(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Complete the config flow after EMS linking."""
        # Create the config entry
        await self.async_set_unique_id(f"{DOMAIN}_oauth")
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title="EKZ Customer Account",
            data={
                CONF_AUTH_TYPE: AUTH_TYPE_OAUTH,
                CONF_EMS_INSTANCE_ID: self.ems_instance_id,
                **self.oauth_data,
            },
        )


class EkzTariffsConfigFlow(OAuth2FlowHandler, config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EKZ Tariffs."""

    VERSION = 1
