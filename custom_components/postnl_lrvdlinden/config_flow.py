"""Config flow for PostNL.

Two ways to link an account:
- ``credentials``: sign in directly with the PostNL e-mail address and password
  (same flow as PostNL for Homey 1.2.6+). The password is only used for the
  login itself; Home Assistant stores the resulting tokens, never the password.
- ``callback``: the original PKCE flow with the Chrome Login Helper, kept as a
  fallback for accounts where the direct login does not work.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import PostNLApi, PostNLAuthError
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_CALLBACK_URL,
    CONF_EMAIL,
    CONF_EXPIRES_AT,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN_TYPE,
    CONF_USERNAME,
    DOMAIN,
    HELPER_URL,
)
from .schema import vol

_LOGGER = logging.getLogger(__name__)
UNIQUE_ID = "postnl_account"


class PostNLConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """UI setup for the PostNL account."""

    VERSION = 1

    def __init__(self) -> None:
        self._pending: dict[str, str] | None = None

    # ------------------------------------------------------------------ entry points
    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        await self.async_set_unique_id(UNIQUE_ID)
        self._abort_if_unique_id_configured()
        return self.async_show_menu(step_id="user", menu_options=["credentials", "callback"])

    async def async_step_reauth(self, entry_data: dict[str, Any]):
        self._pending = None
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None):
        return self.async_show_menu(step_id="reauth_confirm", menu_options=["credentials", "callback"])

    # ------------------------------------------------------------------ e-mail + password
    async def async_step_credentials(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        default_email = ""
        if self.source == config_entries.SOURCE_REAUTH:
            default_email = str(self._get_reauth_entry().data.get(CONF_USERNAME) or "")
            if "@" not in default_email:
                default_email = ""
        if user_input is not None:
            email = str(user_input.get(CONF_EMAIL) or "").strip()
            default_email = email
            api = PostNLApi(async_get_clientsession(self.hass))
            try:
                auth = await api.login_with_password(email, str(user_input.get(CONF_PASSWORD) or ""))
                return await self._async_finish(api, auth, fallback_username=email)
            except PostNLAuthError as err:
                _LOGGER.debug("PostNL password login refused: %s (%s)", err, err.code)
                errors["base"] = "login_changed" if err.code == "AUTH_LOGIN_CHANGED" else "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during PostNL password login")
                errors["base"] = "cannot_connect"

        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL, default=default_email): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
                ),
                vol.Required(CONF_PASSWORD): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
                ),
            }
        )
        return self.async_show_form(step_id="credentials", data_schema=schema, errors=errors)

    # ------------------------------------------------------------------ Chrome helper callback
    async def async_step_callback(self, user_input: dict[str, Any] | None = None):
        if self._pending is None:
            self._pending = PostNLApi.create_authorization()
        errors: dict[str, str] = {}
        if user_input is not None:
            callback_url = str(user_input.get(CONF_CALLBACK_URL) or "").strip()
            api = PostNLApi(async_get_clientsession(self.hass))
            try:
                auth = await api.complete_authorization(
                    callback_url, self._pending["verifier"], self._pending["state"]
                )
                return await self._async_finish(api, auth)
            except PostNLAuthError:
                errors["base"] = "invalid_auth"
                self._pending = PostNLApi.create_authorization()
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during PostNL callback login")
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="callback",
            data_schema=vol.Schema({vol.Required(CONF_CALLBACK_URL): str}),
            errors=errors,
            description_placeholders={"auth_url": self._pending["url"], "helper_url": HELPER_URL},
        )

    # ------------------------------------------------------------------ shared
    async def _async_finish(self, api: PostNLApi, auth: dict[str, Any], fallback_username: str = ""):
        try:
            profile = await api.fetch_profile()
        except Exception:  # noqa: BLE001 - profile is cosmetic, tokens are what matter
            profile = None
        username = str((profile or {}).get("username") or fallback_username or "Mijn PostNL")
        data = {
            CONF_ACCESS_TOKEN: auth.get("access_token"),
            CONF_REFRESH_TOKEN: auth.get("refresh_token"),
            CONF_EXPIRES_AT: auth.get("expires_at"),
            CONF_TOKEN_TYPE: auth.get("token_type") or "Bearer",
            CONF_USERNAME: username,
        }
        if self.source == config_entries.SOURCE_REAUTH:
            await self.async_set_unique_id(UNIQUE_ID)
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(self._get_reauth_entry(), data_updates=data)
        return self.async_create_entry(title=username, data=data)
