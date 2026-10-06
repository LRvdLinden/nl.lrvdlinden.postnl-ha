"""Constants for PostNL by LRvdLinden."""
from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "postnl_lrvdlinden"
NAME = "PostNL"
VERSION = "1.0.0"
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]
UPDATE_INTERVAL = timedelta(seconds=60)
STATIC_URL = f"/{DOMAIN}_static"
FRONTEND_MODULE_URL = f"{STATIC_URL}/postnl-card.js?v={VERSION}"
HELPER_URL = "https://github.com/LRvdLinden/nl.lrvdlinden.postnl-ha/raw/main/tools/PostNL-Home-Assistant-Login-Helper.zip"

CLIENT_ID = "deb0a372-6d72-4e09-83fe-997beacbd137"
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

EVENT_NEW_MAIL = "postnl_new_mail"
EVENT_NEW_PACKAGE = "postnl_new_package"
EVENT_DELIVERY_WINDOW_KNOWN = "postnl_delivery_window_known"
EVENT_PACKAGE_STATUS_CHANGED = "postnl_package_status_changed"
EVENT_SYNC_FAILED = "postnl_sync_failed"
EVENT_LOGIN_EXPIRED = "postnl_login_expired"
