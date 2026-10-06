"""Data coordinator for PostNL."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PostNLApi, PostNLAuthError, PostNLError
from .const import (
    DOMAIN,
    EVENT_DELIVERY_WINDOW_KNOWN,
    EVENT_LOGIN_EXPIRED,
    EVENT_NEW_MAIL,
    EVENT_NEW_PACKAGE,
    EVENT_PACKAGE_STATUS_CHANGED,
    EVENT_SYNC_FAILED,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class PostNLCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll all PostNL account data once per interval."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: PostNLApi) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name="PostNL",
            config_entry=entry,
            update_interval=UPDATE_INTERVAL,
            always_update=True,
        )
        self.entry = entry
        self.api = api
        self.image_cache: dict[str, tuple[str, bytes]] = {}
        self._previous: dict[str, Any] | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            live = await self.api.fetch_all()
            await self._refresh_letter_images(live.get("letters") or [])
            data = {
                **live,
                "updatedAt": datetime.now(timezone.utc).isoformat(),
                "connected": True,
            }
            self._emit_events(self._previous, data)
            self._previous = data
            return data
        except PostNLAuthError as err:
            self.hass.bus.async_fire(EVENT_LOGIN_EXPIRED, {"entry_id": self.entry.entry_id, "error": str(err)})
            raise ConfigEntryAuthFailed(str(err)) from err
        except PostNLError as err:
            self.hass.bus.async_fire(EVENT_SYNC_FAILED, {"entry_id": self.entry.entry_id, "error": str(err)})
            raise UpdateFailed(str(err)) from err
        except Exception as err:
            self.hass.bus.async_fire(EVENT_SYNC_FAILED, {"entry_id": self.entry.entry_id, "error": str(err)})
            raise UpdateFailed(f"PostNL bijwerken mislukt: {err}") from err

    async def _refresh_letter_images(self, letters: list[dict[str, Any]]) -> None:
        live_ids = {str(item.get("id")) for item in letters if item.get("id")}
        self.image_cache = {key: value for key, value in self.image_cache.items() if key in live_ids}
        for item in letters:
            item_id = str(item.get("id") or "")
            url = item.get("imageUrl")
            item["imageAvailable"] = bool(url)
            if not item_id or not url or item_id in self.image_cache:
                continue
            try:
                self.image_cache[item_id] = await self.api.fetch_image(str(url))
            except Exception as err:
                _LOGGER.debug("PostNL mail image fetch failed for %s: %s", item_id, err)

    def active_package(self, data: dict[str, Any] | None = None) -> dict[str, Any] | None:
        packages = list((data or self.data or {}).get("packages") or [])
        active = [p for p in packages if not p.get("delivered")]
        active.sort(key=lambda p: p.get("deliveryWindowFrom") or p.get("deliveryDate") or p.get("createdAt") or "9999")
        return active[0] if active else None

    def _emit_events(self, previous: dict[str, Any] | None, current: dict[str, Any]) -> None:
        if not previous:
            return
        prev_letters = {str(x.get("id")): x for x in previous.get("letters") or []}
        cur_letters = {str(x.get("id")): x for x in current.get("letters") or []}
        for item_id in cur_letters.keys() - prev_letters.keys():
            item = cur_letters[item_id]
            self.hass.bus.async_fire(
                EVENT_NEW_MAIL,
                {
                    "entry_id": self.entry.entry_id,
                    "count": len(cur_letters),
                    "id": item_id,
                    "title": item.get("title") or "",
                    "sender": item.get("sender") or "",
                    "date": item.get("deliveryDate") or "",
                    "unread": bool(item.get("unread")),
                    "image_available": item_id in self.image_cache,
                },
            )

        prev_packages = {str(x.get("id") or x.get("barcode")): x for x in previous.get("packages") or []}
        cur_packages = {str(x.get("id") or x.get("barcode")): x for x in current.get("packages") or []}
        for package_id in cur_packages.keys() - prev_packages.keys():
            p = cur_packages[package_id]
            self.hass.bus.async_fire(EVENT_NEW_PACKAGE, self._package_event_data(p))

        for package_id in cur_packages.keys() & prev_packages.keys():
            old, new = prev_packages[package_id], cur_packages[package_id]
            if str(old.get("statusFingerprint") or old.get("status")) != str(new.get("statusFingerprint") or new.get("status")):
                self.hass.bus.async_fire(EVENT_PACKAGE_STATUS_CHANGED, self._package_event_data(new))
            old_window = bool(old.get("deliveryWindowFrom") or old.get("deliveryWindowTo"))
            new_window = bool(new.get("deliveryWindowFrom") or new.get("deliveryWindowTo"))
            if not old_window and new_window:
                self.hass.bus.async_fire(EVENT_DELIVERY_WINDOW_KNOWN, self._package_event_data(new))

    def _package_event_data(self, p: dict[str, Any]) -> dict[str, Any]:
        return {
            "entry_id": self.entry.entry_id,
            "id": p.get("id") or "",
            "tracking": p.get("barcode") or "",
            "sender": p.get("sender") or "",
            "receiver": p.get("receiver") or "",
            "status": p.get("statusRaw") or p.get("status") or "",
            "event": p.get("latestStatusEvent") or "",
            "status_time": p.get("statusChangedAt") or "",
            "delivery_date": p.get("deliveryDate") or "",
            "delivery_window": p.get("deliveryWindow") or "",
            "delivered": bool(p.get("delivered")),
            "shipment_type": p.get("shipmentType") or "",
        }
