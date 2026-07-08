# AGENTS.md

## Project overview

`ekz_tariffs` is a Home Assistant custom integration (HACS) that exposes EKZ
(Swiss utility) dynamic energy tariffs as sensors, a calendar, and buttons.
It supports two auth modes: a public tariff API (no login, manual tariff
selection) and an OIDC OAuth flow against EKZ's Keycloak realm (confidential
and PKCE/public clients) for personalized customer tariffs.

- Integration code lives under `custom_components/ekz_tariffs/`.
- `const.py` holds domain constants, API endpoints, and OAuth config.
- `oauth_impl.py` / `application_credentials.py` / `config_flow.py` implement
  the OAuth2 + PKCE flow on top of `homeassistant.helpers.config_entry_oauth2_flow`.
- `api.py` holds the HTTP clients for the public and OAuth-authenticated APIs.
- `coordinator.py` / `sensor.py` / `calendar.py` / `button.py` are the HA
  platform entities.
- Tests live in `tests/ekz_tariffs/`, mirroring the module under test.

Runtime dependencies are managed by Home Assistant itself via
`manifest.json`, not pip — `pyproject.toml` is for local tooling
(lint/test/type-check) only.

## Setup commands

Create/activate the venv and install dev tooling (matches CI):

```bash
python -m venv .venv && source .venv/bin/activate
pip install pytest pytest-asyncio pytest-homeassistant-custom-component ruff mypy types-requests
```

## Build, lint, and test commands

Run these before considering any change done — they match `.github/workflows/ci.yml` exactly:

```bash
ruff check .              # lint
ruff format --check .     # formatting
pytest -q                 # test suite
mypy custom_components    # type check (informational only — CI runs this with continue-on-error)
```

To scope a single test file during iteration: `pytest tests/ekz_tariffs/test_oauth_impl.py -v`.

Note: `mypy` in this repo currently has a pre-existing, unrelated failure
caused by a stale `build/` artifact (gitignored) creating a duplicate module
path, plus a `python_version` mismatch against the installed Home Assistant
package's syntax. This is why CI treats mypy as non-blocking — don't try to
silence it by suppressing errors in code you touch; if it's actually your
change causing a new mypy failure, fix that, but don't chase the pre-existing
`build/`-artifact error.

## Code style

- Python 3.12+ (repo declares `requires-python = ">=3.12"`; CI runs on 3.13).
- Formatting/linting via `ruff` (line length 88, `E`/`F`/`W`/`I`/`B`/`UP`/`SIM`/`RUF` rule sets — see `pyproject.toml`).
- `from __future__ import annotations` at the top of every module.
- Follow existing Home Assistant integration conventions: async everywhere,
  config entries over YAML config, `hass.helpers.aiohttp_client.async_get_clientsession(hass)`
  for HTTP calls rather than ad-hoc `aiohttp.ClientSession()` instances.
- No comments explaining *what* code does — only non-obvious *why* (a hidden
  constraint, a workaround, a subtle invariant).
- Auth-type naming: `AUTH_TYPE_PUBLIC`/`AUTH_TYPE_OAUTH` (in `const.py`) mean
  "public tariff API vs. customer OAuth login" — do not confuse this with
  OIDC "public client" (PKCE, no client_secret), which is a separate concept
  handled inside `oauth_impl.py` (`_is_public_client`). Avoid introducing
  naming that conflates the two.

## Testing instructions

- Framework: `pytest` + `pytest-asyncio` + `pytest-homeassistant-custom-component`
  (provides the `hass` fixture, `aioclient_mock` for mocking HTTP calls made
  via `async_get_clientsession`, and `MockConfigEntry`).
- `asyncio_mode = "auto"` is set in `pyproject.toml`, so `async def test_...`
  functions run without needing `@pytest.mark.asyncio` (existing tests still
  add the marker for clarity — follow that convention).
- Shared fixtures/helpers live in `tests/conftest.py` (`mock_config_entry`,
  `hass_time_zone`, `make_slots`, `fixed_now`/`patch_now`).
- When adding coverage for HTTP-calling code, prefer `aioclient_mock` over
  monkeypatching `aiohttp.ClientSession` directly — it only intercepts calls
  made through `async_get_clientsession`, which is the pattern the codebase
  already uses.
- Every new feature or bug fix should land with a corresponding test in
  `tests/ekz_tariffs/`.

## PR / commit instructions

- Keep changes scoped; this integration intentionally avoids
  backwards-compatibility shims and speculative abstractions.
- If a change affects the integration `version` in
  `custom_components/ekz_tariffs/manifest.json`, note that the release
  workflow (`.github/workflows/release.yml`) requires the pushed tag
  (`vX.Y.Z` or `X.Y.Z`) to exactly match `manifest.json`'s `version` field,
  or the release job fails.
- `.github/workflows/validate.yml` runs HACS and Hassfest validation on every
  push — structural changes to `manifest.json`, `hacs.json`, or the platform
  files should keep those checks in mind (e.g. required manifest keys,
  correct `domain`/`integration_type`).
- User-facing behavior changes (new config options, new auth modes, etc.)
  should also update `readme.md` and, for anything OAuth-related,
  `OAUTH_SETUP.md`.
