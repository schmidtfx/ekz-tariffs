# OAuth Setup Documentation for EKZ Tariffs Integration

This document provides detailed information about setting up OAuth authentication with the EKZ Tariffs API for Home Assistant.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [OAuth Flow Architecture](#oauth-flow-architecture)
- [Step-by-Step Setup Guide](#step-by-step-setup-guide)
- [Technical Implementation Details](#technical-implementation-details)
- [Troubleshooting](#troubleshooting)
- [API Reference](#api-reference)

## Overview

The EKZ Tariffs integration supports OAuth 2.0 authentication using the **OpenID Connect (OIDC) Authorization Code Flow**, for both **confidential clients** (client_id + client_secret) and **public clients** (client_id only, using PKCE). This authentication method allows the integration to:

- Retrieve personalized customer tariffs via the protected `/customerTariffs` endpoint
- Automatically receive the correct tariffs for your specific metering point
- Stay synchronized with any tariff assignment changes made by EKZ
- Access EMS (Energy Management System) linking functionality

### Why Use OAuth?

**For End Users:**
- ✅ Automatic tariff detection - no manual tariff selection required
- ✅ Always up-to-date with your actual assigned tariffs
- ✅ Access to customer-specific pricing and configurations
- ✅ Future-proof as EKZ updates tariff assignments

**For Energy Management Systems (EMS):**
- ✅ EKZ recommends OAuth for EMS implementations
- ✅ Ensures correct tariffs are retrieved at all times
- ✅ Potential inclusion in EKZ's official compatibility list
- ✅ Professional-grade integration with proper authentication

## Prerequisites

Before you can use OAuth authentication with this integration, you need:

1. **A myEKZ Customer Account**
   - You must be an EKZ customer with an active account

2. **OAuth Client Credentials from EKZ**
   - `client_id` - Your unique client identifier
   - `client_secret` - Your confidential client secret (**only issued for confidential clients**; public/PKCE clients receive a `client_id` only)
   - These must be requested from EKZ (see below)

3. **Home Assistant with Application Credentials Support**
   - Home Assistant Core 2023.8 or later recommended
   - Access to Home Assistant settings/configuration

### Requesting OAuth Credentials from EKZ

To obtain OAuth credentials for the EKZ Tariffs API:

1. **Contact EKZ** via their official form or support channels
   - Request form: [EKZ EMS Connection Request](https://forms.office.com/Pages/ResponsePage.aspx?id=XqcHk8gVZkSibazU0UTTpczKnf9BpR1ErQgdpIRN1u1UNThURkhZTjI1TjhLV1pLUzJNR1M2OThWTiQlQCN0PWcu&r12784a0e65bd412da19fd29d26f2e4fc=https%3A%2F%2F)
   - Mention that you want to connect an Energy Management System (EMS)
   - Specify that you need OAuth credentials for API access

2. **Provide Required Information:**
   - Your customer details and contract number
   - Description of your use case (e.g., "Home Assistant integration for tariff monitoring")
   - Your redirect URI: `https://my.home-assistant.io/redirect/oauth`
   - Or if you're using a custom redirect: `https://<your-home-assistant-url>/auth/external/callback`

3. **Wait for Approval:**
   - EKZ will review your request
   - Upon approval, you'll receive:
     - `client_id` - Your OAuth client identifier
     - `client_secret` - Your OAuth client secret (keep this confidential!)

4. **Keep Credentials Secure:**
   - Store your credentials securely
   - Never share your `client_secret` publicly
   - Do not commit credentials to version control

## OAuth Flow Architecture

The integration uses the **OAuth 2.0 Authorization Code Flow** as specified by EKZ:

```
┌─────────────────┐                                    ┌──────────────────┐
│                 │                                    │                  │
│  Home Assistant │                                    │   myEKZ Portal   │
│   Integration   │                                    │   (Keycloak)     │
│                 │                                    │                  │
└────────┬────────┘                                    └────────┬─────────┘
         │                                                      │
         │ 1. User initiates OAuth setup                       │
         ├─────────────────────────────────────────────────────>│
         │    Redirect to authorization endpoint               │
         │    with client_id and scopes                        │
         │                                                      │
         │                                                      │ 2. User logs in
         │                                                      │    and authorizes
         │                                                      │
         │ 3. Authorization code returned                      │
         │<─────────────────────────────────────────────────────┤
         │    via redirect URI                                 │
         │                                                      │
         │ 4. Exchange code for tokens                         │
         ├─────────────────────────────────────────────────────>│
         │    POST with Authorization: Basic header            │
         │    (base64 encoded client_id:client_secret)         │
         │                                                      │
         │ 5. Receive access & refresh tokens                  │
         │<─────────────────────────────────────────────────────┤
         │    - access_token (valid 30 min)                    │
         │    - refresh_token (valid 30 days)                  │
         │                                                      │
         │                                                      │
┌────────▼────────┐                                    ┌────────▼─────────┐
│                 │                                    │                  │
│   Home Assistant│     6. Check EMS link status      │   EKZ Tariffs    │
│   w/ Tokens     ├──────────────────────────────────>│      API         │
│                 │     GET /v1/emsLinkStatus          │                  │
│                 │     Bearer <access_token>          │                  │
│                 │                                    │                  │
│                 │     7. Response: link_required     │                  │
│                 │<──────────────────────────────────┤                  │
│                 │     or linked                      │                  │
│                 │                                    │                  │
│                 │                                    │                  │
│   (If link      │ 8. User completes EMS linking     │                  │
│    required)    │    via provided URL                │                  │
│                 │                                    │                  │
│                 │     9. Fetch customer tariffs      │                  │
│                 ├──────────────────────────────────>│                  │
│                 │     GET /v1/customerTariffs        │                  │
│                 │     Bearer <access_token>          │                  │
│                 │                                    │                  │
│                 │     10. Customer tariffs data      │                  │
│                 │<──────────────────────────────────┤                  │
│                 │                                    │                  │
└─────────────────┘                                    └──────────────────┘
```

**Note:** The diagram above shows the **confidential-client** token exchange
(step 4). Public (PKCE) clients omit the `Authorization: Basic` header
entirely and instead include `client_id` and `code_verifier` in the request
body. Public clients also add `code_challenge`/`code_challenge_method=S256`
to the authorization redirect in step 1. See
[PKCE (Public Clients)](#pkce-public-clients) below for details.

### Key Components

1. **Authorization Endpoint**
   - URL: `https://login.ekz.ch/auth/realms/myEKZ/protocol/openid-connect/auth`
   - User logs in and grants permission

2. **Token Endpoint**
   - URL: `https://login.ekz.ch/auth/realms/myEKZ/protocol/openid-connect/token`
   - Exchanges authorization code for tokens
   - Refreshes expired access tokens

3. **Protected API Endpoints**
   - `/v1/emsLinkStatus` - Check EMS linking status
   - `/v1/customerTariffs` - Retrieve customer-specific tariffs

## Step-by-Step Setup Guide

### Part 1: Configure Application Credentials in Home Assistant

1. **Navigate to Application Credentials:**
   - Open Home Assistant
   - Go to **Settings** → **Devices & Services** → **Application Credentials**
   - Or use this shortcut: [![Open Application Credentials](https://my.home-assistant.io/badges/application_credentials.svg)](https://my.home-assistant.io/redirect/application_credentials/)

2. **Add EKZ Dynamic Tariffs Credentials:**
   - Click **+ Add Application Credential** button
   - Select **"EKZ Dynamic Tariffs"** from the dropdown
   - Enter your credentials received from EKZ:
     - **Client ID**: Your `client_id` from EKZ
     - **Client Secret**: Your `client_secret` from EKZ (**leave this field blank if EKZ issued you a public/PKCE client** — the integration automatically detects this and uses PKCE instead of HTTP Basic authentication)
   - Click **Submit**

3. **Verify Credentials Are Saved:**
   - You should see "EKZ Dynamic Tariffs" listed with a partially masked Client ID
   - The credentials are now stored securely in Home Assistant

### Part 2: Add the Integration with OAuth

1. **Start Integration Setup:**
   - Go to **Settings** → **Devices & Services** → **Integrations**
   - Click **+ Add Integration** button
   - Search for **"EKZ Dynamic Tariffs"**
   - Click on the integration

2. **Choose Authentication Method:**
   - Select **"Customer Account (OAuth - personalized tariffs)"**
   - Click **Submit**

3. **Complete OAuth Flow:**
   - You'll be redirected to the myEKZ login page
   - **Log in** with your myEKZ customer credentials (username/password)
   - **Review the permissions** requested by the integration:
     - `openid` - Basic OpenID Connect authentication
     - `offline_access` - Allows token refresh without re-login
   - Click **Authorize** or **Allow** to grant access

4. **Return to Home Assistant:**
   - You'll be automatically redirected back to Home Assistant
   - The integration will complete the setup
   - You should see a success message

### Part 3: Complete EMS Linking (First-Time Only)

After OAuth authentication, you must link your Home Assistant instance to your EKZ metering point. This is a one-time process.

1. **Check EMS Link Status:**
   - The integration automatically checks if linking is required
   - If linking is needed, you'll see a **"EMS Link Status"** binary sensor with state `OFF`

2. **Get the Linking URL:**
   - Check the **"EMS Link Status"** sensor attributes
   - Look for the `linking_url` attribute
   - Or enable the **"EMS Linking URL"** sensor to see it directly

3. **Complete the Linking Process:**
   - Click or copy the linking URL
   - You'll be taken to the myEKZ portal
   - **Select your metering point** from the list
   - **Confirm the connection** between your Home Assistant and the selected metering point
   - Complete any additional confirmation steps

4. **Verify Linking:**
   - Return to Home Assistant
   - Run the service: `ekz_tariffs.check_ems_link_status`
   - The **"EMS Link Status"** sensor should now show `ON` (linked)

5. **Start Receiving Tariffs:**
   - Once linked, the integration will automatically fetch your customer tariffs
   - All sensors will update with your personalized pricing data

## Technical Implementation Details

### OAuth Implementation

The integration uses a **custom OAuth2 implementation** with the following key features:

#### HTTP Basic Authentication (Confidential Clients)

This applies only to confidential clients (those with a `client_secret`). Unlike standard OAuth implementations, EKZ requires confidential client credentials to be sent via **HTTP Basic authentication** header:

```python
# Encode credentials as Base64
credentials = f"{client_id}:{client_secret}"
encoded = base64.b64encode(credentials.encode()).decode()

# Add to request header
headers = {
    "Authorization": f"Basic {encoded}",
    "Content-Type": "application/x-www-form-urlencoded",
}
```

**Note:** The `client_id` and `client_secret` are NOT sent in the request body.

#### PKCE (Public Clients)

Public clients (registered with EKZ without a `client_secret`) authenticate
using [PKCE](https://datatracker.ietf.org/doc/html/rfc7636) (Proof Key for
Code Exchange) instead of a shared secret:

- A random `code_verifier` is generated per authorization attempt.
- Its SHA-256 hash (`code_challenge`, method `S256`) is sent on the
  authorization redirect.
- The original `code_verifier` is sent in the token exchange request body,
  proving the token request comes from the same client that started the
  flow — no client secret is ever needed.

The integration reuses Home Assistant core's built-in
`LocalOAuth2ImplementationWithPkce` helpers (`generate_code_verifier` /
`compute_code_challenge`) for this rather than implementing PKCE crypto
itself.

#### Token Exchange

**Authorization Code Grant (confidential client):**
```http
POST https://login.ekz.ch/auth/realms/myEKZ/protocol/openid-connect/token
Authorization: Basic <base64(client_id:client_secret)>
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code&
code=<authorization_code>&
redirect_uri=<redirect_uri>
```

**Authorization Code Grant (public client, PKCE):**
```http
POST https://login.ekz.ch/auth/realms/myEKZ/protocol/openid-connect/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code&
code=<authorization_code>&
redirect_uri=<redirect_uri>&
client_id=<client_id>&
code_verifier=<code_verifier>
```

**Response:**
```json
{
  "access_token": "eyJhbGci...",
  "expires_in": 1800,
  "refresh_expires_in": 2592000,
  "refresh_token": "eyJhbGci...",
  "token_type": "Bearer",
  "id_token": "eyJhbGci...",
  "session_state": "...",
  "scope": "openid email profile offline_access"
}
```

#### Token Refresh

**Refresh Token Grant (confidential client):**
```http
POST https://login.ekz.ch/auth/realms/myEKZ/protocol/openid-connect/token
Authorization: Basic <base64(client_id:client_secret)>
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token&
refresh_token=<refresh_token>
```

**Refresh Token Grant (public client):**
```http
POST https://login.ekz.ch/auth/realms/myEKZ/protocol/openid-connect/token
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token&
refresh_token=<refresh_token>&
client_id=<client_id>
```

The integration automatically refreshes tokens when needed using the stored refresh token.

### Token Lifecycle

| Token Type | Validity | Max Uses | Notes |
|------------|----------|----------|-------|
| **Access Token** | 30 minutes | Unlimited | Used for API requests |
| **Refresh Token** | 30 days | 10 uses | Used to obtain new access tokens |

**Important:** After 10 refresh token uses OR 30 days, the user must re-authenticate through the OAuth flow.

### Required OAuth Scopes

The integration requests the following scopes:

- **`openid`** - Required for OpenID Connect authentication
- **`offline_access`** - Required to receive a refresh token for long-term access

These scopes are defined in `const.py`:
```python
OAUTH2_SCOPES = ["openid", "offline_access"]
```

### API Endpoints Used

#### 1. Check EMS Link Status
```http
GET https://api.tariffs.ekz.ch/v1/emsLinkStatus
Authorization: Bearer <access_token>

Query Parameters:
  - ems_instance_id: Unique identifier for your Home Assistant instance
  - redirect_uri: Where to redirect after linking
```

**Response when linking required:**
```json
{
  "link_status": "link_required",
  "linking_process_redirect_uri": "https://www.ekz.ch/link?token=..."
}
```

**Response when linked:**
```json
{
  "link_status": "linked"
}
```

#### 2. Get Customer Tariffs
```http
GET https://api.tariffs.ekz.ch/v1/customerTariffs
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "tariffs": [
    {
      "tariff_type": "energy",
      "tariff_name": "400D",
      "start_timestamp": "2026-02-13T00:00:00+01:00",
      "end_timestamp": "2026-02-13T00:15:00+01:00",
      "price": {
        "chf_per_kwh": 0.2345
      }
    },
    // ... more tariff entries
  ]
}
```

### Files Involved in OAuth Implementation

1. **`oauth_impl.py`** - Custom OAuth2 implementation with HTTP Basic auth
2. **`application_credentials.py`** - Application credentials platform integration
3. **`config_flow.py`** - Configuration flow with OAuth support
4. **`api.py`** - API client that uses OAuth tokens for authenticated requests
5. **`const.py`** - OAuth endpoints, scopes, and API URLs

## Troubleshooting

### Common Issues and Solutions

#### 1. "Failed to Exchange Authorization Code"

**Symptoms:** Error during OAuth flow after clicking "Authorize"

**Possible Causes:**
- Incorrect client credentials
- Wrong redirect URI configured at EKZ
- Network connectivity issues

**Solutions:**
- Verify your Client ID and Client Secret in Application Credentials
- Ensure the redirect URI matches what you provided to EKZ
- Check Home Assistant logs for detailed error messages

#### 2. "EMS Link Required" - Linking URL Not Working

**Symptoms:** Linking URL doesn't load or shows an error

**Possible Causes:**
- Expired or invalid access token
- Incorrect EMS instance ID
- Browser blocking cookies/redirects

**Solutions:**
- Try refreshing the EMS link status: `ekz_tariffs.check_ems_link_status`
- Clear browser cache and cookies
- Try using a different browser
- Check if you're logged into myEKZ in the same browser

#### 3. "401 Unauthorized" When Fetching Tariffs

**Symptoms:** Sensors show unavailable, error logs mention 401

**Possible Causes:**
- Access token expired and refresh failed
- Refresh token expired (after 30 days or 10 uses)
- EMS link was removed or expired

**Solutions:**
- Check token expiration in integration logs
- Re-authenticate by removing and re-adding the integration
- Verify EMS link status is still "linked"

#### 4. Refresh Token Expired

**Symptoms:** Integration stops updating after 30 days

**Cause:** Refresh token has expired or reached maximum uses

**Solution:**
- Remove the integration configuration
- Re-add the integration and complete OAuth flow again
- Consider automating periodic re-authentication reminders

#### 5. "Invalid Redirect URI"

**Symptoms:** OAuth flow fails with redirect URI error

**Cause:** The redirect URI doesn't match what's registered with EKZ

**Solutions:**
- Verify you're using: `https://my.home-assistant.io/redirect/oauth`
- Or if custom: `https://<your-domain>/auth/external/callback`
- Contact EKZ to update the registered redirect URI

### Debugging OAuth Issues

Enable debug logging for detailed OAuth flow information:

```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.ekz_tariffs: debug
    homeassistant.components.application_credentials: debug
    homeassistant.helpers.config_entry_oauth2_flow: debug
```

Check the logs in **Settings** → **System** → **Logs** for detailed error messages.

### Testing OAuth Flow

To test the OAuth flow without affecting your production setup:

1. Use the test environment endpoints (commented out in `const.py`):
   ```python
   # Test endpoints
   OAUTH2_AUTHORIZE = "https://login-test.ekz.ch/auth/realms/myEKZ/protocol/openid-connect/auth"
   OAUTH2_TOKEN = "https://login-test.ekz.ch/auth/realms/myEKZ/protocol/openid-connect/token"
   API_BASE = "https://test-api.tariffs.ekz.ch/v1"
   ```

2. Request test credentials from EKZ
3. Test the full flow in a development environment

## API Reference

### OAuth Endpoints

| Endpoint | Purpose | Method |
|----------|---------|--------|
| `https://login.ekz.ch/auth/realms/myEKZ/protocol/openid-connect/auth` | Authorization endpoint | GET |
| `https://login.ekz.ch/auth/realms/myEKZ/protocol/openid-connect/token` | Token endpoint | POST |

### Protected API Endpoints

| Endpoint | Purpose | Auth Required |
|----------|---------|---------------|
| `/v1/tariffs` | Public tariffs (no auth) | ❌ No |
| `/v1/emsLinkStatus` | Check EMS link status | ✅ OAuth |
| `/v1/customerTariffs` | Customer-specific tariffs | ✅ OAuth |

### OAuth Parameters

**Authorization Request:**
- `client_id` - Your client identifier
- `redirect_uri` - Where to redirect after auth
- `response_type` - Always `code`
- `scope` - Space-separated: `openid offline_access`

**Token Request:**
- `grant_type` - `authorization_code` or `refresh_token`
- `code` - Authorization code (for code grant)
- `refresh_token` - Refresh token (for refresh grant)
- `redirect_uri` - Must match authorization request

### Rate Limits and Caching

- **Tariff Updates:** Daily at 18:00 for next day
- **API Quota:** Respect rate limits (not explicitly documented)
- **Caching:** Tariffs are stable once published - cache aggressively
- **Recommendation:** Fetch once daily, cache results locally

### Daylight Saving Time

Be aware of DST transitions:

| Season | Date Example | Tariff Count | Notes |
|--------|--------------|--------------|-------|
| Spring (DST start) | 2025-03-30 | 92 tariffs | Hour 02:00-02:59 does not exist |
| Autumn (DST end) | 2025-10-26 | 100 tariffs | Hour 02:00-02:59 occurs twice |

The API handles DST transitions automatically in the timestamp format.

## Additional Resources

- **EKZ API Swagger Documentation:** https://api.tariffs.ekz.ch/swagger/index.html
- **myEKZ Customer Portal:** https://www.ekz.ch/de/privatkunden/service/meinekz/meinekz-oeffnen.html
- **Home Assistant OAuth Documentation:** https://www.home-assistant.io/integrations/application_credentials/
- **Integration Repository:** https://github.com/schmidtfx/ekz-tariffs

## Security Considerations

### Credential Storage

- Client credentials are stored securely in Home Assistant's credential storage
- Tokens are encrypted and stored in the config entry
- Never expose your `client_secret` in logs or publicly

### Token Security

- Access tokens are short-lived (30 minutes)
- Refresh tokens expire after 30 days or 10 uses
- Tokens are transmitted over HTTPS only
- Use Home Assistant's built-in token refresh mechanism

### Network Security

- All API communication uses HTTPS/TLS
- Ensure Home Assistant is properly secured with SSL/TLS
- Use strong passwords for myEKZ account
- Consider using fail2ban for additional security

## Support

If you encounter issues with OAuth setup:

1. Check this documentation thoroughly
2. Review Home Assistant logs with debug enabled
3. Verify credentials with EKZ
4. Open an issue on GitHub: https://github.com/schmidtfx/ekz-tariffs/issues
5. Contact EKZ support for API-related issues

---

**Document Version:** 1.0  
**Last Updated:** February 13, 2026  
**Integration Version:** Compatible with ekz-tariffs v1.0.0+
