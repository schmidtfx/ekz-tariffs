from homeassistant.const import Platform

DOMAIN = "ekz_tariffs"
PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.CALENDAR, Platform.SENSOR]

CONF_TARIFF_NAME = "tariff_name"
CONF_AUTH_TYPE = "auth_type"
CONF_EMS_INSTANCE_ID = "ems_instance_id"
CONF_INCLUDE_VAT = "include_vat"
AUTH_TYPE_PUBLIC = "public"
AUTH_TYPE_OAUTH = "oauth"
DEFAULT_TARIFF_NAME = "400D"

API_BASE = "https://api.tariffs.ekz.ch/v1"
# API_BASE = "https://test-api.tariffs.ekz.ch/v1"
API_TARIFFS_PATH = "/tariffs"
API_CUSTOMER_TARIFFS_PATH = "/customerTariffs"
API_EMS_LINK_STATUS_PATH = "/emsLinkStatus"

# OAuth2 Configuration
OAUTH2_AUTHORIZE = "https://login.ekz.ch/auth/realms/myEKZ/protocol/openid-connect/auth"
OAUTH2_TOKEN = "https://login.ekz.ch/auth/realms/myEKZ/protocol/openid-connect/token"
# OAUTH2_AUTHORIZE = "https://login-test.ekz.ch/auth/realms/myEKZ/protocol/openid-connect/auth"
# OAUTH2_TOKEN = "https://login-test.ekz.ch/auth/realms/myEKZ/protocol/openid-connect/token"
OAUTH2_SCOPES = ["openid", "offline_access"]

INTEGRATED_PREFIX = "integrated_"

FETCH_HOUR = 18
FETCH_MINUTE = 30

EVENT_TYPE = f"{DOMAIN}_event"
EVENT_TARIFF_START = "tariff_start"

SERVICE_REFRESH = "refresh"
SERVICE_CHECK_EMS_LINK_STATUS = "check_ems_link_status"

VAT_RATE = 0.081
