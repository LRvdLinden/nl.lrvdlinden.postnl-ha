"""Authenticated websocket API for mail images used by Lovelace cards."""
from __future__ import annotations

import base64

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .schema import vol


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/get_mail_image",
        vol.Required("entry_id"): str,
        vol.Required("mail_id"): str,
    }
)
@callback
def ws_get_mail_image(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Return a live PostNL mail scan through the authenticated HA websocket."""
    entry_id = msg["entry_id"]
    mail_id = msg["mail_id"]
    entry = hass.config_entries.async_get_entry(entry_id)
    if not entry or entry.domain != DOMAIN or not entry.runtime_data:
        connection.send_error(msg["id"], "not_found", "PostNL configuration not found")
        return
    cached = entry.runtime_data.image_cache.get(mail_id)
    if not cached:
        connection.send_error(msg["id"], "not_found", "Mail image not available")
        return
    content_type, content = cached
    connection.send_result(
        msg["id"],
        {"content_type": content_type, "content": base64.b64encode(content).decode("ascii")},
    )


def async_register(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_get_mail_image)
