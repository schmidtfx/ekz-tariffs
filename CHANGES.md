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
