# EKZ Dynamic Tariffs

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
![GitHub Release](https://img.shields.io/github/v/release/schmidtfx/ekz-tariffs)
![GitHub License](https://img.shields.io/github/license/schmidtfx/ekz-tariffs)

This is the EKZ tariffs API integration for Home Assistant.

## Features

- **Two Authentication Methods:**
  - **Public API**: Select grid and regional-fee products; electricity is inferred
  - **OAuth (NEW)**: Authenticate with your EKZ customer account to automatically retrieve your personalized tariffs
- Refreshes latest energy prices every day at 6:30pm
- Lets you customize all entities this integration provides (every entity has a unique ID)
- Provides electricity, grid, regional-fee, integrated, integrated-complete, and feed-in price sensors
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
Select the grid product and regional-fee region. The electricity product is determined automatically from the grid product. This doesn't require authentication with EKZ.

**Configuration Variables:**

| Name | Type | Default | Description |
| :--- | :--- | :------ | :---------- |
| `grid_product` | `enum` | `400D` | `400D`, `400F`, `400ST`, `400WP`, `400L`, `400LS`, `16L`, `16LS` |
| `region` | `enum` | Required | `lt500MWh_ZH`, `gt500MWh_ZH`, `Menzingen`, `Einsiedeln` |
| `include_vat` | `boolean` | `false` | Applies VAT to consumption-price sensors; feed-in prices are not VAT-adjusted |

Select the actual regional-fee product for your tariff. To use prices without
regional fees, use the `integrated` sensor instead of `integrated_complete`.

The electricity product is inferred from EKZ's integrated-product mapping:
`400D` uses `dynamic`; `400F`, `400ST`, and `400WP` use `standard`; `400L`,
`400LS`, `16L`, and `16LS` use `business`.

#### 2. Customer Account (OAuth - Personalized Tariffs)
Select this option to authenticate with your EKZ customer account and automatically retrieve your personalized tariff data.

**Prerequisites:**
- You need OAuth credentials (Client ID, and Client Secret if EKZ issued you a confidential client) from EKZ
- You must have a myEKZ customer account

**OAuth Setup:**

📖 **[Complete OAuth Setup Guide](OAUTH_SETUP.md)** - Comprehensive documentation with detailed instructions, troubleshooting, and technical details.

**Quick Start:**

1. **Request OAuth Credentials from EKZ:**
   - Contact EKZ via their [official form](https://forms.office.com/Pages/ResponsePage.aspx?id=XqcHk8gVZkSibazU0UTTpczKnf9BpR1ErQgdpIRN1u1UNThURkhZTjI1TjhLV1pLUzJNR1M2OThWTiQlQCN0PWcu&r12784a0e65bd412da19fd29d26f2e4fc=https%3A%2F%2F)
   - Request OAuth credentials for API access
   - Provide your redirect URI: `https://my.home-assistant.io/redirect/oauth`
   - Wait for approval and receive your Client ID and Client Secret

2. **Configure Application Credentials in Home Assistant:**
   - Go to **Settings** ➤ **Devices & Services** ➤ **Application Credentials**
   - Click ➕ **Add Application Credential**
   - Select "EKZ Dynamic Tariffs"
   - Enter your Client ID and Client Secret received from EKZ
   - Click **Submit**

   *If EKZ issued you a **public/PKCE client** (Client ID only, no secret), skip this step — the integration's own setup flow will ask you to choose "Public / PKCE" and enter just your Client ID.*

3. **Add the Integration:**
   - Go to **Settings** ➤ **Devices & Services** ➤ **Integrations**
   - Click ➕ **Add Integration**
   - Search for "EKZ Dynamic Tariffs"
   - Choose "Customer Account (OAuth - personalized tariffs)"
   - Follow the OAuth flow to authenticate with your myEKZ account
   - Complete the EMS linking process (one-time setup)

**OAuth Benefits:**
- ✅ Automatically retrieves tariffs specific to your metering point
- ✅ No need to manually select tariff plans
- ✅ Access to customer-specific API endpoints
- ✅ Stays synchronized with tariff assignment changes

**Need Help?** See the [OAuth Setup Documentation](OAUTH_SETUP.md) for troubleshooting, technical details, and advanced configuration.

## Sensors

This integration provides multiple sensors to help you monitor and optimize your energy consumption based on dynamic tariff prices.

### Sensors Overview

| Sensor Name | Type | Unit | Enabled by Default | Description |
| :---------- | :--- | :--- | :----------------- | :---------- |
| Energy tariff | Sensor | CHF/kWh | ❌ | Electricity component (`..._electricity`) |
| Grid usage tariff | Sensor | CHF/kWh | ❌ | Grid component (`..._grid`) |
| Regional charges | Sensor | CHF/kWh | ❌ | Regional-fee component (`..._regional_fees`) |
| Consumption tariff | Sensor | CHF/kWh | ✅ | Total: grid + electricity + regional fees (`..._integrated_complete`) |
| Basic tariff | Sensor | CHF/kWh | ✅ | Grid + electricity, excluding regional fees (`..._integrated`) |
| Feed-in tariff | Sensor | CHF/kWh | ✅ | Feed-in component (`..._feed_in`) |
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

The six price sensors share these attributes:

- `tariff_name`: selected tariff product for public setups; `null` for customer-specific OAuth data
- `publication_timestamp`: EKZ publication time (or fetch time when not supplied by the API)
- `slot_start` / `slot_end`: bounds of the current priced slot
- `next_change`: next time the sensor's price changes
- `forecast`: available future slots as `[start_timestamp, price]` pairs, ordered by timestamp

The forecast contains only slots whose start is after now. Unpublished prices are omitted, and the
forecast can cover today and tomorrow when EKZ has published both days. Its timestamps carry local
time-zone offsets, so consumers should parse the timestamp instead of assuming 96 slots per day.
The `forecast` attribute is excluded from recorder history; historical prices come from the sensor's
recorded state.

**Breaking changes in 0.9.0:** `feed_in` replaces the previous `feed_in_price` entity, and the
existing `current_price` entity is migrated to `integrated_complete`, retaining its price history
and representing the total price, including regional fees. The `none` region option has been
removed; select your region, and use the new `integrated` sensor when regional fees should be
excluded.
`raw_today`, `raw_tomorrow`, and feed-in `schedule` are replaced by `forecast`. Update charts that
use those old attributes. Recorder has no supported attribute-only purge, so existing historical
states and their large forecast attributes are kept; new forecast values are not recorded.

Example [apexcharts-card](https://github.com/RomRider/apexcharts-card) configuration combining
recorded history with the future forecast:

```yaml
type: custom:apexcharts-card
graph_span: 48h
span:
  start: day
header:
  show: true
  title: EKZ Dynamic Prices
series:
  - entity: sensor.ekz_400d_integrated_complete
    name: History
    type: column
    color: yellow
    opacity: 1
  - entity: sensor.ekz_400d_integrated_complete
    name: Forecast
    type: column
    color: yellow
    opacity: 0.5
    data_generator: |
      return (entity.attributes.forecast || []).map(([start, price]) => [
        new Date(start).getTime(),
        price
      ]);
```

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
  - `min_price_start` / `min_price_end`: Start and end of the cheapest block of the day (the earliest one if the price occurs more than once)
  - `max_price_chf_per_kwh`: Maximum price of the day
  - `max_price_start` / `max_price_end`: Start and end of the most expensive block of the day (the earliest one if the price occurs more than once)
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
