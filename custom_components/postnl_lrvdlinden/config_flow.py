"""Config flow for PostNL."""
from __future__ import annotations

from typing import Any

import probatio
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PostNLApi, PostNLAuthError
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_EXPIRES_AT,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN_TYPE,
    CONF_USERNAME,
    DOMAIN,
    HELPER_URL,
)


class PostNLConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """UI setup for the PostNL PKCE login."""

    VERSION = 1

    def __init__(self) -> None:
        self._pending: dict[str, str] | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        await self.async_set_unique_id("postnl_account")
        self._abort_if_unique_id_configured()
        return await self._async_login_step("user", user_input)

    async def _async_login_step(self, step_id: str, user_input: dict[str, Any] | None):
        if self._pending is None:
            self._pending = PostNLApi.create_authorization()
        errors: dict[str, str] = {}
        if user_input is not None:
            callback_url = str(user_input.get("callback_url") or "").strip()
            try:
                api = PostNLApi(async_get_clientsession(self.hass))
                auth = await api.complete_authorization(
                    callback_url, self._pending["verifier"], self._pending["state"]
                )
                profile = await api.fetch_profile()
                username = str((profile or {}).get("username") or "Mijn PostNL")
                data = {
                    CONF_ACCESS_TOKEN: auth.get("access_token"),
                    CONF_REFRESH_TOKEN: auth.get("refresh_token"),
                    CONF_EXPIRES_AT: auth.get("expires_at"),
                    CONF_TOKEN_TYPE: auth.get("token_type") or "Bearer",
                    CONF_USERNAME: username,
                }
                if self.source == config_entries.SOURCE_REAUTH:
                    await self.async_set_unique_id("postnl_account")
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data_updates=data
                    )
                return self.async_create_entry(title=username, data=data)
            except PostNLAuthError:
                errors["base"] = "invalid_auth"
                self._pending = PostNLApi.create_authorization()
            except Exception:
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id=step_id,
            data_schema=probatio.Schema({probatio.Required("callback_url"): str}),
            errors=errors,
            description_placeholders={
                "auth_url": self._pending["url"],
                "helper_url": HELPER_URL,
            },
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]):
        self._pending = None
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None):
        return await self._async_login_step("reauth_confirm", user_input)
