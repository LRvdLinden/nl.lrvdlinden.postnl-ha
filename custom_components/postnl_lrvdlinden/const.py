"""Constants for PostNL by LRvdLinden."""
from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "postnl_lrvdlinden"
NAME = "PostNL"
VERSION = "1.1.0"
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]
UPDATE_INTERVAL = timedelta(seconds=60)
STATIC_URL = f"/{DOMAIN}_static"
FRONTEND_MODULE_URL = f"{STATIC_URL}/postnl-card-v105.js?v={VERSION}"
HELPER_URL = "https://github.com/LRvdLinden/nl.lrvdlinden.postnl-ha/raw/main/tools/PostNL-Home-Assistant-Login-Helper.zip"

CLIENT_ID = "deb0a372-6d72-4e09-83fe-997beacbd137"
# Client used by the PostNL Capture/Hosted Login widget during e-mail/password login.
CAPTURE_CLIENT_ID = "dkyxkt9x888ye422mawmf769yfm9y44j"
CAPTURE_FLOW_VERSION = "20250910094830574377"
LOGIN_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
)
TENANT = "101112a0-4a0f-4bbb-8176-2f1b2d370d7c"
AUTH_URL = f"https://login.postnl.nl/{TENANT}/login/authorize"
TOKEN_URL = f"https://login.postnl.nl/{TENANT}/login/token"
REDIRECT_URI = "postnl://login"
SCOPE = "profile openid email address phone poa-profiles-api"
GRAPHQL_URL = "https://jouw.postnl.nl/account/api/graphql"
MYMAIL_URL = "https://jouw.postnl.nl/services/serverdrivenui/api/MyMail/letter"
TRACK_API_URL = "https://jouw.postnl.nl/track-and-trace/api/trackAndTrace"

CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_EXPIRES_AT = "expires_at"
CONF_TOKEN_TYPE = "token_type"
CONF_USERNAME = "username"
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_CALLBACK_URL = "callback_url"

CANONICAL_STATUSES = [
    "registered",
    "in_transit",
    "out_for_delivery",
    "at_pickup_point",
    "delivered",
    "returning",
    "unknown",
]

EVENT_NEW_MAIL = "postnl_new_mail"
EVENT_NEW_PACKAGE = "postnl_new_package"
EVENT_DELIVERY_WINDOW_KNOWN = "postnl_delivery_window_known"
EVENT_PACKAGE_STATUS_CHANGED = "postnl_package_status_changed"
EVENT_PACKAGE_DELIVERED = "postnl_package_delivered"
EVENT_DELIVERY_WINDOW_CHANGED = "postnl_delivery_window_changed"
EVENT_PACKAGE_EVENT_CHANGED = "postnl_package_event_changed"
EVENT_PACKAGE_WEIGHT_KNOWN = "postnl_package_weight_known"
EVENT_PACKAGE_DIMENSIONS_KNOWN = "postnl_package_dimensions_known"
EVENT_SYNC_FAILED = "postnl_sync_failed"
EVENT_LOGIN_EXPIRED = "postnl_login_expired"
