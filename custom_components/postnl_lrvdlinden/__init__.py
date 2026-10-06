"""PostNL integration for Home Assistant, ported from PostNL for Homey."""
from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PostNLApi
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_EXPIRES_AT,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN_TYPE,
    DOMAIN,
    FRONTEND_MODULE_URL,
    PLATFORMS,
    STATIC_URL,
)
from .coordinator import PostNLCoordinator
from .websocket import async_register as async_register_websocket


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    if not hass.data.get(f"{DOMAIN}_websocket_registered"):
        async_register_websocket(hass)
        hass.data[f"{DOMAIN}_websocket_registered"] = True

    if not hass.data.get(f"{DOMAIN}_frontend_registered"):
        frontend_path = Path(__file__).parent / "frontend"
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, str(frontend_path), True)]
        )
        add_extra_js_url(hass, FRONTEND_MODULE_URL)
        hass.data[f"{DOMAIN}_frontend_registered"] = True

    async def handle_refresh(call: ServiceCall) -> None:
        for entry in hass.config_entries.async_entries(DOMAIN):
            coordinator = entry.runtime_data
            if coordinator:
                await coordinator.async_request_refresh()

    if not hass.services.has_service(DOMAIN, "refresh"):
        hass.services.async_register(DOMAIN, "refresh", handle_refresh)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    async def token_update(auth: dict) -> None:
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_ACCESS_TOKEN: auth.get("access_token"),
                CONF_REFRESH_TOKEN: auth.get("refresh_token"),
                CONF_EXPIRES_AT: auth.get("expires_at"),
                CONF_TOKEN_TYPE: auth.get("token_type") or "Bearer",
            },
        )

    auth = {
        "access_token": entry.data.get(CONF_ACCESS_TOKEN),
        "refresh_token": entry.data.get(CONF_REFRESH_TOKEN),
        "expires_at": entry.data.get(CONF_EXPIRES_AT),
        "token_type": entry.data.get(CONF_TOKEN_TYPE) or "Bearer",
    }
    api = PostNLApi(async_get_clientsession(hass), auth=auth, token_update_cb=token_update)
    coordinator = PostNLCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
