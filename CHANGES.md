# Version 0.6.1

*Follow-up fix that makes public / PKCE OAuth clients actually configurable — the 0.6.0 approach didn't work end-to-end.*

## Fixes

**Public (PKCE) OAuth clients are now actually usable** ([#9](../../pull/9))

The 0.6.0 guidance was "leave the Client Secret field blank in the Application Credentials form" — but Home Assistant's frontend enforces `vol.Required` string fields as non-empty client-side (screenshot: "OAuth-Client-Geheimnis* — Erforderlich"), so users couldn't actually submit the form for a public client. Fixed by giving public clients their own path through the integration's config flow:

- After choosing "Customer Account (OAuth)", a new step asks whether EKZ issued you a **Confidential** (Client ID + Client Secret) or **Public / PKCE** (Client ID only) client.
- The Confidential path continues to use Application Credentials (unchanged).
- The Public path bypasses Application Credentials entirely: it asks for the Client ID in a dedicated form, registers the OAuth implementation programmatically, and hands off to the standard OAuth authorization step. The Client ID is persisted on the config entry so the implementation can be re-registered on every Home Assistant restart.
- Translations for the two new steps added in en / de / fr / it.
- Docs updated accordingly: `OAUTH_SETUP.md` and `readme.md` no longer suggest leaving Client Secret blank.

## Internal

- New `EkzTariffsConfigFlow` steps `async_step_oauth_client_type` and `async_step_public_client_config` handle client-type selection and public-client ID entry.
- `async_setup_entry` re-registers the public-client `EKZOAuth2Implementation` on startup from the stored `client_id` before looking it up.
- 4 new config-flow tests cover the client-type choice, the form, implementation registration + client_id trimming, and the confidential-path routing.

---

# Version 0.6.0

*Two feature additions since v0.5.1, both backward-compatible — no action needed for existing installations.*

## New Features

**Regional fee surcharges** ([#6](../../pull/6))

EKZ's integrated tariffs (e.g. `integrated_400F`) exclude regional fees such as the Förderung Energieeffizienz surcharge — EKZ provides these as separate tariffs. This release lets you include them automatically:
- **Public API setups**: pick your regional fee from a new dropdown (Zürich <500MWh, Zürich ≥500MWh, Menzingen, Einsiedeln) and it's summed into the displayed price.
- **OAuth (customer account) setups**: a checkbox sums the `regional_fees` already returned alongside `integrated` tariffs by `/v1/customerTariffs` — no extra API call needed.
- Prices are now rounded to 4 decimal places, matching EKZ's own tariff sheets.

**Public (PKCE) OAuth clients** ([#8](../../pull/8))

The OAuth customer-account flow previously assumed every client was confidential (client ID + client secret sent via HTTP Basic auth). It now also supports **public clients** — for users whom EKZ issues only a client ID:
- Client type is auto-detected: leave **Client Secret** blank in Home Assistant's Application Credentials form to register a public client.
- Public clients authenticate via PKCE (`code_challenge`/`code_verifier`, S256) instead of a shared secret, on both the initial token exchange and refresh.
- Confidential-client behavior is completely unchanged.
- See the updated [OAuth Setup Guide](OAUTH_SETUP.md) for details on both client types.

## Internal

- OAuth token requests now use Home Assistant's shared, connection-pooled HTTP session instead of a one-off session per call.
- Added test coverage for both confidential and public OAuth client paths.
- Added `AGENTS.md` with project conventions for AI coding agents.

## Thanks

A special thank you to [@IngmarStein](https://github.com/IngmarStein) for their **first contribution** to this project — the regional fee surcharge support in #6. Much appreciated! 🎉

---

# Version 0.4.0 - OAuth Support

## Summary

Added OAuth2 authentication support to the EKZ Tariffs integration, allowing users to authenticate with their myEKZ customer account to retrieve personalized tariff data.

## Changes

### New Files
- `custom_components/ekz_tariffs/application_credentials.py` - OAuth application credentials configuration
- `custom_components/ekz_tariffs/strings.json` - UI translations for config flow
- `OAUTH_SETUP.md` - Comprehensive OAuth implementation guide

### Modified Files

#### `custom_components/ekz_tariffs/const.py`
- Added `CONF_AUTH_TYPE`, `AUTH_TYPE_PUBLIC`, `AUTH_TYPE_OAUTH` constants
- Added OAuth API endpoints: `API_CUSTOMER_TARIFFS_PATH`, `API_EMS_LINK_STATUS_PATH`
- Added OAuth2 configuration: `OAUTH2_AUTHORIZE`, `OAUTH2_TOKEN`, `OAUTH2_SCOPES`

#### `custom_components/ekz_tariffs/config_flow.py`
- Completely restructured to support both public and OAuth flows
- Added `OAuth2FlowHandler` class extending `AbstractOAuth2FlowHandler`
- Added `async_step_auth_type()` for authentication method selection
- Added `async_step_public_config()` for public API configuration
- Added `async_oauth_create_entry()` for OAuth completion
- Updated unique_id generation to differentiate between auth types

#### `custom_components/ekz_tariffs/api.py`
- Refactored `EkzTariffsApi` class (public API client)
- Added `EkzTariffsOAuthApi` class for authenticated endpoints
- Added `CustomerTariff` and `EMSLinkStatus` dataclasses
- Implemented `fetch_customer_tariffs()` method
- Implemented `fetch_ems_link_status()` method
- Added automatic token refresh via `_get_headers()`

#### `custom_components/ekz_tariffs/coordinator.py`
- Added `EkzTariffsOAuthCoordinator` class for OAuth-based coordination
- Both coordinators now clearly documented for their respective purposes

#### `custom_components/ekz_tariffs/__init__.py`
- Added conditional setup based on `auth_type`
- Implemented OAuth2Session management for OAuth entries
- Added OAuth token handling and session creation
- Maintained backward compatibility with existing public API entries

#### `custom_components/ekz_tariffs/manifest.json`
- Added `"application_credentials"` dependency
- Updated version to `0.4.0`

#### `readme.md`
- Added OAuth authentication documentation
- Added OAuth setup instructions (3-step process)
- Added OAuth benefits and technical details
- Restructured configuration section

## Authentication Methods

### 1. Public API (Existing - No Changes)
- Manually select tariff name
- No authentication required
- Endpoint: `/v1/tariffs`
- Multiple instances allowed (one per tariff)

### 2. OAuth Customer Account (New)
- Authenticate with myEKZ account
- Automatic personalized tariff retrieval
- Endpoint: `/v1/customerTariffs`
- Additional endpoint: `/v1/emsLinkStatus`
- Single instance allowed

## OAuth Flow

1. User selects "Customer Account (OAuth)" during integration setup
2. User must have configured application credentials beforehand
3. OAuth authorization flow initiated with EKZ login
4. User authenticates with myEKZ credentials
5. Access and refresh tokens stored securely
6. Tokens automatically refreshed when needed

## Backward Compatibility

✅ Existing public API installations continue to work unchanged
✅ No migration required for existing users
✅ New `auth_type` field defaults to "public" for old entries

## Security

- OAuth tokens stored securely in Home Assistant's encrypted storage
- Access tokens valid for 30 minutes
- Refresh tokens valid for 30 days (max 10 uses)
- Automatic token refresh before API calls
- Client credentials managed via Home Assistant's application credentials system

## Next Steps

1. Test the OAuth flow with actual EKZ credentials
2. Test public API flow (regression test)
3. Consider adding EMS link status as a binary sensor
4. Consider adding additional OAuth-only features if available
