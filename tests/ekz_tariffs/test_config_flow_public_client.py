from __future__ import annotations

import pytest
from custom_components.ekz_tariffs.const import (
    AUTH_IMPL_PUBLIC_CLIENT,
    AUTH_TYPE_OAUTH,
    CONF_AUTH_TYPE,
    CONF_CLIENT_ID,
    CONF_OAUTH_CLIENT_TYPE,
    DOMAIN,
    OAUTH_CLIENT_TYPE_CONFIDENTIAL,
    OAUTH_CLIENT_TYPE_PUBLIC,
)
from custom_components.ekz_tariffs.oauth_impl import EKZOAuth2Implementation
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow


@pytest.mark.asyncio
async def test_oauth_selection_prompts_for_client_type(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "auth_type"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AUTH_TYPE: AUTH_TYPE_OAUTH}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "oauth_client_type"


@pytest.mark.asyncio
async def test_public_client_choice_shows_client_id_form(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AUTH_TYPE: AUTH_TYPE_OAUTH}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_OAUTH_CLIENT_TYPE: OAUTH_CLIENT_TYPE_PUBLIC}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "public_client_config"


@pytest.mark.asyncio
async def test_public_client_id_registers_implementation(
    hass: HomeAssistant, current_request_with_host
):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AUTH_TYPE: AUTH_TYPE_OAUTH}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_OAUTH_CLIENT_TYPE: OAUTH_CLIENT_TYPE_PUBLIC}
    )
    # Submit the public client_id — this should register a public-client
    # implementation and advance past pick_implementation into the OAuth
    # authorize external step (which we don't drive further here).
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CLIENT_ID: "  test-public-client  "}
    )

    impls = await config_entry_oauth2_flow.async_get_implementations(hass, DOMAIN)
    assert AUTH_IMPL_PUBLIC_CLIENT in impls
    impl = impls[AUTH_IMPL_PUBLIC_CLIENT]
    assert isinstance(impl, EKZOAuth2Implementation)
    # client_id must be stripped (leading/trailing whitespace)
    assert impl.client_id == "test-public-client"
    # No client_secret → public client → PKCE verifier generated
    assert impl._is_public_client is True
    assert impl._pkce_code_verifier is not None


@pytest.mark.asyncio
async def test_confidential_choice_aborts_without_credentials(hass: HomeAssistant):
    """With no Application Credentials configured, the confidential path
    should route into HA's pick_implementation logic and abort with a
    missing_credentials/missing_configuration reason — proving we don't
    accidentally intercept confidential flows."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_AUTH_TYPE: AUTH_TYPE_OAUTH}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_OAUTH_CLIENT_TYPE: OAUTH_CLIENT_TYPE_CONFIDENTIAL}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] in {"missing_credentials", "missing_configuration"}
