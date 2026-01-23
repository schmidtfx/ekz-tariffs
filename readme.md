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

## Sensors

This integration provides multiple sensors to help you monitor and optimize your energy consumption based on dynamic tariff prices.

### Sensors Overview

| Sensor Name | Type | Unit | Enabled by Default | Description |
| :---------- | :--- | :--- | :----------------- | :---------- |
| Current price | Sensor | CHF/kWh | ✅ | Current electricity price |
| Next change | Sensor | Timestamp | ✅ | When the price will next change |
| Average price today | Sensor | CHF/kWh | ✅ | Average price for today with statistics |
| Average price tomorrow | Sensor | CHF/kWh | ❌ | Average price for tomorrow with statistics |
| Lowest 2h window today | Sensor | CHF/kWh | ❌ | Average price of cheapest 2h consecutive window today |
| Lowest 2h window tomorrow | Sensor | CHF/kWh | ❌ | Average price of cheapest 2h consecutive window tomorrow |
| Lowest 4h window today | Sensor | CHF/kWh | ❌ | Average price of cheapest 4h consecutive window today |
| Lowest 4h window tomorrow | Sensor | CHF/kWh | ❌ | Average price of cheapest 4h consecutive window tomorrow |
| Highest 2h window today | Sensor | CHF/kWh | ❌ | Average price of most expensive 2h consecutive window today |
| Highest 2h window tomorrow | Sensor | CHF/kWh | ❌ | Average price of most expensive 2h consecutive window tomorrow |
| Highest 4h window today | Sensor | CHF/kWh | ❌ | Average price of most expensive 4h consecutive window today |
| Highest 4h window tomorrow | Sensor | CHF/kWh | ❌ | Average price of most expensive 4h consecutive window tomorrow |
| Cheapest 25% hours today | Binary | - | ❌ | ON if current hour is in cheapest 25% of hours |
| Cheapest 10% hours today | Binary | - | ❌ | ON if current hour is in cheapest 10% of hours |
| Cheapest 50% hours today | Binary | - | ❌ | ON if current hour is in cheapest 50% of hours |
| Most expensive 25% hours today | Binary | - | ❌ | ON if current hour is in most expensive 25% of hours |
| Most expensive 10% hours today | Binary | - | ❌ | ON if current hour is in most expensive 10% of hours |
| In cheapest 2h window today | Binary | - | ❌ | ON if currently in the cheapest 2h consecutive window |
| In cheapest 4h window today | Binary | - | ❌ | ON if currently in the cheapest 4h consecutive window |
| In most expensive 2h window today | Binary | - | ❌ | ON if currently in the most expensive 2h consecutive window |
| In most expensive 4h window today | Binary | - | ❌ | ON if currently in the most expensive 4h consecutive window |
| EMS link status* | Binary | - | ✅ | OAuth only: Shows EMS connection status |
| EMS linking URL* | Sensor | - | ❌ | OAuth only: Provides EMS linking URL when needed |

*Only available when using OAuth authentication

### Price Sensors

#### Current Price
- **Entity ID**: `sensor.<entry_name>_current_price`
- **Unit**: CHF/kWh
- **Description**: Shows the current electricity price
- **Attributes**:
  - `schedule_date`: Date of the current schedule
  - `next_change`: Timestamp when the price will next change
  - `slot_start`: Start time of the current price slot
  - `slot_end`: End time of the current price slot
  - `tariff_name`: Name of your tariff plan (if using Public API)

#### Next Change
- **Entity ID**: `sensor.<entry_name>_next_change`
- **Type**: Timestamp sensor
- **Description**: Indicates when the price will next change
- **Attributes**:
  - `slot_start`: Start time of the current slot
  - `slot_end`: End time of the current slot
  - `tariff_name`: Name of your tariff plan (if using Public API)

### Daily Statistics Sensors

#### Average Price Today
- **Entity ID**: `sensor.<entry_name>_average_price_today`
- **Unit**: CHF/kWh
- **Description**: Shows the average electricity price for today
- **Attributes**:
  - `day`: Date for which the average is calculated
  - `min_price_chf_per_kwh`: Minimum price of the day
  - `max_price_chf_per_kwh`: Maximum price of the day
  - `median_price_chf_per_kwh`: Median price of the day
  - `q25_price_chf_per_kwh`: 25th percentile price
  - `q75_price_chf_per_kwh`: 75th percentile price
  - `slots_count`: Number of price slots
  - `covered_minutes`: Total minutes covered by slots

#### Average Price Tomorrow
- **Entity ID**: `sensor.<entry_name>_average_price_tomorrow`
- **Unit**: CHF/kWh
- **Description**: Shows the average electricity price for tomorrow (disabled by default)
- **Attributes**: Same as "Average Price Today"

### Window Extreme Sensors

These sensors identify the time windows with the lowest or highest average prices for consecutive hours.

#### Lowest/Highest 2-Hour Windows
- **Entity IDs**: 
  - `sensor.<entry_name>_lowest_2h_window_today`
  - `sensor.<entry_name>_lowest_2h_window_tomorrow`
  - `sensor.<entry_name>_highest_2h_window_today`
  - `sensor.<entry_name>_highest_2h_window_tomorrow`
- **Unit**: CHF/kWh
- **Description**: Shows the average price of the lowest/highest 2-hour consecutive window
- **Attributes**:
  - `window_start`: Start time of the window
  - `window_end`: End time of the window
  - `window_minutes`: Duration of the window (120)
  - `mode`: Either "min" or "max"
  - `date`: Date for which the window is calculated

#### Lowest/Highest 4-Hour Windows
- **Entity IDs**: 
  - `sensor.<entry_name>_lowest_4h_window_today`
  - `sensor.<entry_name>_lowest_4h_window_tomorrow`
  - `sensor.<entry_name>_highest_4h_window_today`
  - `sensor.<entry_name>_highest_4h_window_tomorrow`
- **Unit**: CHF/kWh
- **Description**: Shows the average price of the lowest/highest 4-hour consecutive window
- **Attributes**: Same as 2-hour windows, but with `window_minutes`: 240

### Quantile Sensors (Binary)

These binary sensors indicate if the current hour falls within a certain percentage of cheapest/most expensive hours of the day.

#### Cheapest Hours Sensors
- **Entity IDs**: 
  - `binary_sensor.<entry_name>_cheapest_25_percent_hours_today` *(disabled by default)*
  - `binary_sensor.<entry_name>_cheapest_10_percent_hours_today` *(disabled by default)*
  - `binary_sensor.<entry_name>_cheapest_50_percent_hours_today` *(disabled by default)*
- **Description**: ON when the current hour is in the cheapest X% of hours today
- **Attributes**:
  - `current_hour`: The current hour (0-23)
  - `current_hour_price`: Price for the current hour
  - `threshold_price_Xth_percentile`: Price threshold for the percentile
  - `cheap_hours`: List of hours that qualify as cheap
  - `hourly_prices`: All hourly prices for the day
  - `quantile`: The quantile value (0.25, 0.10, 0.50)
  - `mode`: "cheapest"

#### Most Expensive Hours Sensors
- **Entity IDs**: 
  - `binary_sensor.<entry_name>_most_expensive_25_percent_hours_today` *(disabled by default)*
  - `binary_sensor.<entry_name>_most_expensive_10_percent_hours_today` *(disabled by default)*
- **Description**: ON when the current hour is in the most expensive X% of hours today
- **Attributes**:
  - Similar to cheapest hours sensors, but with `expensive_hours` instead of `cheap_hours`
  - `mode`: "most_expensive"

### In Window Sensors (Binary)

These binary sensors indicate if the current time falls within the cheapest/most expensive consecutive time window.

#### In Cheapest Window Sensors
- **Entity IDs**: 
  - `binary_sensor.<entry_name>_in_cheapest_2h_window_today` *(disabled by default)*
  - `binary_sensor.<entry_name>_in_cheapest_4h_window_today` *(disabled by default)*
- **Description**: ON when currently in the cheapest 2h/4h consecutive window of today
- **Attributes**:
  - `window_start`: Start time of the cheapest window
  - `window_end`: End time of the cheapest window
  - `window_average_price`: Average price during this window
  - `window_hours`: Duration in hours (2 or 4)
  - `mode`: "cheapest"
  - `in_window`: Boolean indicating if currently in the window

#### In Most Expensive Window Sensors
- **Entity IDs**: 
  - `binary_sensor.<entry_name>_in_most_expensive_2h_window_today` *(disabled by default)*
  - `binary_sensor.<entry_name>_in_most_expensive_4h_window_today` *(disabled by default)*
- **Description**: ON when currently in the most expensive 2h/4h consecutive window of today
- **Attributes**: Same as cheapest window sensors, but with `mode`: "most_expensive"

### OAuth-Specific Sensors

These sensors are only available when using OAuth authentication with your EKZ customer account.

#### EMS Link Status (Binary)
- **Entity ID**: `binary_sensor.<entry_name>_ems_link_status`
- **Device Class**: Connectivity
- **Description**: Shows if your Home Assistant instance is linked to EKZ's Energy Management System (EMS)
- **State**: ON = Linked, OFF = Link required or error
- **Attributes**:
  - `ems_instance_id`: Your EMS instance identifier
  - `linking_url`: URL to complete the linking process (if required)
  - `last_error`: Error message (if any)

#### EMS Linking URL
- **Entity ID**: `sensor.<entry_name>_ems_linking_url` *(disabled by default)*
- **Description**: Provides the URL needed to link your Home Assistant to EKZ's EMS
- **State**: "Link required" or "Linked"
- **Attributes**:
  - `linking_url`: The URL to visit for linking (when link is required)
- **Availability**: Only available when linking is required

## Service Actions

### Service Actions Overview

| Service Name | Description | Parameters | OAuth Only |
| :----------- | :---------- | :--------- | :--------- |
| `ekz_tariffs.refresh` | Fetch EKZ tariffs now and update calendar/sensors | `entry_id` (optional) | ❌ |
| `ekz_tariffs.check_ems_link_status` | Check EMS linking status and update status sensors | None | ✅ |

### Refresh Tariffs

**Service**: `ekz_tariffs.refresh`

Triggers an immediate update of the energy prices, calendar, and all sensors.

**Parameters**:
- `entry_id` (optional): Home Assistant config entry ID to refresh only one EKZ Tariffs instance. If omitted, refreshes all EKZ Tariffs entries.
  - Example: `"a1b2c3d4e5f6g7h8i9j0"`

**Example**:
```yaml
service: ekz_tariffs.refresh
data:
  entry_id: "a1b2c3d4e5f6g7h8i9j0"
```

### Check EMS Link Status

**Service**: `ekz_tariffs.check_ems_link_status`

Checks the EMS linking status for OAuth configurations and updates the EMS status sensors. This service is only available for OAuth-based integrations.

**Parameters**: None

**Example**:
```yaml
service: ekz_tariffs.check_ems_link_status
```
