# Unreleased

## New Features

**Raw 15-minute price arrays on the Current price sensor** ([#4](../../issues/4))

The forward price data was already being fetched (the coordinator pulls today + tomorrow) but was only reachable through the `hourly_prices` attribute on the quantile binary sensors — which is today-only and keyed by hour `0-23`. At 22:00 that leaves two usable data points, so charting "the next 12h" or computing a dishwasher delay across midnight wasn't possible.

`sensor.<entry_name>_current_price` now carries three new attributes:

- `raw_today` — flat list of 15-minute prices for today, indexed from local midnight.
- `raw_tomorrow` — the same for tomorrow, a full-length list of `null` until EKZ publishes (typically by 18:00).
- `publication_timestamp` — when the data was last fetched from EKZ, persisted across restarts.

The arrays are registered as unrecorded attributes, so they do not grow the recorder database despite changing every 15 minutes. `readme.md` has a ready-to-use apexcharts-card example.

**Timestamps for the daily minimum and maximum price** ([#10](../../issues/10))

`sensor.<entry_name>_average_price_today` (and `..._tomorrow`) already reported `min_price_chf_per_kwh` / `max_price_chf_per_kwh`, but not *when* those prices occur, so answering "when is it cheapest today" meant re-deriving it from the raw arrays. Four new attributes carry the extremes' slot bounds as local ISO timestamps:

- `min_price_start` / `min_price_end`
- `max_price_start` / `max_price_end`

Because EKZ publishes 15-minute slots that routinely repeat a price, the span covers the whole contiguous block at the extreme price rather than just its first quarter hour — a flat cheap night reads `02:00` → `04:00`, not `02:00` → `02:15`. If the price occurs again later in the day the earliest block wins, and a block straddling midnight is clamped, so the timestamps always fall inside the sensor's `day`.

## Fixes

**Median and quartiles on the average sensor included the next day's prices**

`daily_stats()` scoped `avg`/`min`/`max` to the requested day but computed `median_price_chf_per_kwh`, `q25_price_chf_per_kwh` and `q75_price_chf_per_kwh` over *every* slot the coordinator held. Once EKZ published tomorrow's tariffs (typically 18:00), today's quantiles silently became two-day quantiles. All quantiles are now taken from the same day-scoped slots as the rest of the statistics.

**Daily statistics were off by an hour on DST transition days**

`_day_range_local` treated a local day as exactly 24 hours. Combined with the fact that Python does wall-clock arithmetic when both operands share a `ZoneInfo`, the 15-minute bucketing produced 96 buckets on every day — so on the spring-forward day the last four buckets held *the next day's* prices, and on the fall-back day the final hour was dropped. Day bounds are now computed from consecutive local midnights and all bucketing/overlap maths runs in UTC, so a local day yields 92 / 96 / 100 buckets as appropriate. This affects `Average price today/tomorrow` and the `Lowest/Highest Nh window` sensors on those two days per year.

**Feed-in `schedule` attribute is no longer written to the recorder**

The ~192-entry `schedule` list was being stored in history on every state change.

## Internal

- New `statistics.day_slot_prices()` returns the 15-minute price list for a local day; `bucket_prices()` now walks the day in UTC and `_advance()` re-normalises offsets across DST.
- Coordinators record `last_fetched` and persist it as `fetched_at` in the per-entry `Store`; the key is additive, so existing caches load unchanged.
- `EkzCurrentPriceSensor` schedules an explicit midnight timer — `fuse_slots()` merges adjacent equal prices, so there is not always a price boundary at midnight to trigger the day rollover.
- New tests: `tests/ekz_tariffs/test_raw_prices.py` and `tests/ekz_tariffs/test_statistics.py` (the first coverage of `statistics.py`).

---

# Version 0.7.0

*Adds solar feed-in tariffs. Backward-compatible — existing installations pick up the new sensor automatically, and cached tariff data from 0.6.x still loads.*

## New Features

**Feed-in price sensor** ([#11](../../pull/11))

EKZ returns a `feed_in` component alongside the consumption price, but the integration was discarding it. It is now parsed and surfaced through a new sensor:

- `sensor.<entry_name>_feed_in_price` — the current feed-in tariff (Einspeisevergütung), enabled by default, updating at each 15-minute slot boundary.
- A `schedule` attribute carries the **full today + tomorrow slot schedule** as a list of `{start, end, feed_in_chf_per_kwh}` entries, so the forward feed-in curve can be charted directly.
- VAT follows the existing `include_vat` option, applied to the feed-in value on both the public and OAuth code paths.
- Entity name translated in en / de / fr / it.

Works with both authentication types: the OAuth `/customerTariffs` response already includes `feed_in`, and the public `/tariffs` response is parsed the same way.

## Internal

- `TariffSlot` gains an optional `feed_in_chf_per_kwh` field, defaulting to `None` so slots without feed-in data (and older cached entries) remain valid.
- New `_extract_chf_kwh()` helper in `api.py` replaces three hand-rolled copies of the "find the component whose `unit` is `CHF_kWh`" loop across the integrated, regional-fee and feed-in parsers.
- The per-entry `Store` now persists `feed_in` with each slot. The key is read with `.get()`, so caches written by 0.6.x load without a storage version bump.
- `EkzFeedInPriceSensor` subclasses `EkzCurrentPriceSensor` but overrides boundary scheduling: `fuse_slots()` keys on the consumption price, so feed-in boundaries have to be derived from the slots directly.
- New `tests/ekz_tariffs/test_feed_in.py` covers the sensor end-to-end plus feed-in parsing with and without VAT; `make_slots()` in `conftest.py` takes an optional parallel `feed_in` list.

---

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
