# EKZ Dynamic Tariffs

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
![GitHub Release](https://img.shields.io/github/v/release/schmidtfx/ekz-tariffs)
![GitHub License](https://img.shields.io/github/license/schmidtfx/ekz-tariffs)

This is the EKZ tariffs API integration for Home Assistant.

## Features

- **Two Authentication Methods:**
  - **Public API**: Manually select your energy tariff (400D, 400F, 400ST, 400WP, 400L, 400LS, 16L, 16LS)
  - **OAuth (NEW)**: Authenticate with your EKZ customer account to automatically retrieve your personalized tariffs
- Refreshes latest energy prices every day at 6:30pm
- Let's you customize all entities this integration provides (every entity has a unique ID)
- Provides current energy price
- Provides a timestamp for the next change of the energy price
- Provides sensors to indicate the most expensive and cheapest hours for today and tomorrow

## Installation

There are two ways this integration can be installed into Home Assistant.

The easiest and recommended way is to install the integration using HACS, which makes future updates easy to track and install.

Alternatively, installation can be done manually copying the files in this repository into `custom_components` directory in the Home Assistant configuration directory:

1. Open the configuration directory of your Home Assistant installation.
2. If you do not have a custom_components directory, create it.
3. In the custom_components directory, create a new directory called `ekz_tariffs`.
4. Copy all files from the `custom_components/ekz_tariffs/` directory in this repository into the `ekz_tariffs` directory.
5. Restart Home Assistant.
6. Add the integration to Home Assistant (see **Configuration**).

## Configuration

Configuration is done through the Home Assistant UI.

To add the integration, go to **Settings** ➤ **Devices & Services** ➤ **Integrations**, click ➕ **Add Integration**, and search for "EKZ Dynamic Tariffs".

### Authentication Methods

When adding the integration, you'll be asked to choose an authentication method:

#### 1. Public API (Manual Tariff Selection)
Select this option if you want to manually choose your tariff plan. This doesn't require any authentication with EKZ.

**Configuration Variables:**

| Name | Type | Default | Description |
| :--- | :--- | :------ | :---------- |
| `tariff_name` | `enum` | `400D` | 400D, 400F, 400ST, 400WP, 400L, 400LS, 16L, 16LS |

#### 2. Customer Account (OAuth - Personalized Tariffs)
Select this option to authenticate with your EKZ customer account and automatically retrieve your personalized tariff data.

**Prerequisites:**
- You need OAuth credentials (Client ID and Client Secret) from EKZ
- You must have a myEKZ customer account

**OAuth Setup:**

1. **Request OAuth Credentials from EKZ:**
   - Contact EKZ to request OAuth API access
   - Fill out their OAuth application form
   - Wait for approval and receive your Client ID and Client Secret

2. **Configure Application Credentials in Home Assistant:**
   - Go to **Settings** ➤ **Devices & Services** ➤ **Application Credentials**
   - Click ➕ **Add Application Credential**
   - Select "EKZ Dynamic Tariffs"
   - Enter your Client ID and Client Secret received from EKZ
   - Click **Submit**

3. **Add the Integration:**
   - Go to **Settings** ➤ **Devices & Services** ➤ **Integrations**
   - Click ➕ **Add Integration**
   - Search for "EKZ Dynamic Tariffs"
   - Choose "Customer Account (OAuth - personalized tariffs)"
   - Follow the OAuth flow to authenticate with your myEKZ account
   - Authorize Home Assistant to access your tariff data

**OAuth Benefits:**
- Automatically retrieves tariffs specific to your metering point
- No need to manually select tariff plans
- Access to additional customer-specific API endpoints

**OAuth Technical Details:**
- Authorization URL: `https://login.ekz.ch/auth/realms/myEKZ/protocol/openid-connect/auth`
- Token URL: `https://login.ekz.ch/auth/realms/myEKZ/protocol/openid-connect/token`
- Scopes: `openid`, `offline_access`
- Access tokens valid for 30 minutes
- Refresh tokens valid for 30 days (up to 10 usages)

## Service Actions

### EKZ Tariffs: Refresh

`ekz_tariffs.refresh`

Triggers an update of the energy prices.
