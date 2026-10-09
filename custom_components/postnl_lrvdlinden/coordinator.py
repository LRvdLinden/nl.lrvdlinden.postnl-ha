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
    EVENT_DELIVERY_WINDOW_CHANGED,
    EVENT_DELIVERY_WINDOW_KNOWN,
    EVENT_LOGIN_EXPIRED,
    EVENT_NEW_MAIL,
    EVENT_NEW_PACKAGE,
    EVENT_PACKAGE_DELIVERED,
    EVENT_PACKAGE_DIMENSIONS_KNOWN,
    EVENT_PACKAGE_EVENT_CHANGED,
    EVENT_PACKAGE_STATUS_CHANGED,
    EVENT_PACKAGE_WEIGHT_KNOWN,
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
            await self._emit_events(self._previous, data)
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

    @staticmethod
    def _rank(p: dict[str, Any]) -> str:
        return str(p.get("deliveryWindowFrom") or p.get("deliveryDate") or p.get("createdAt") or "9999")

    def active_package(self, data: dict[str, Any] | None = None) -> dict[str, Any] | None:
        packages = list((data or self.data or {}).get("packages") or [])
        active = [p for p in packages if not p.get("delivered")]
        active.sort(key=self._rank)
        return active[0] if active else None

    def journey_package(self, data: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Parcel shown on the 'Reis van je pakket' card: first active parcel with Track & Trace events."""
        packages = list((data or self.data or {}).get("packages") or [])
        candidates = [p for p in packages if not p.get("delivered") and p.get("statusEvents")]
        candidates.sort(key=self._rank)
        return candidates[0] if candidates else None

    @staticmethod
    def _identity(p: dict[str, Any]) -> str:
        # Prefer the stable tracking number: PostNL's internal key can change between syncs.
        return str(p.get("barcode") or p.get("id") or "").strip()

    @staticmethod
    def _has_window(p: dict[str, Any]) -> bool:
        return bool(str(p.get("deliveryWindow") or "").strip() or p.get("deliveryWindowFrom") or p.get("deliveryWindowTo"))

    @staticmethod
    def _event_text(p: dict[str, Any]) -> str:
        return str(p.get("latestStatusEvent") or p.get("statusRaw") or p.get("status") or "")

    @staticmethod
    def _fingerprint(p: dict[str, Any]) -> str:
        return str(p.get("statusFingerprint") or p.get("status") or "")

    def _fire(self, event: str, data: dict[str, Any]) -> None:
        self.hass.bus.async_fire(event, data)

    async def _emit_events(self, previous: dict[str, Any] | None, current: dict[str, Any]) -> None:
        # First successful poll after (re)start is the baseline: never fire for existing items.
        if not previous:
            return
        prev_letters = {str(x.get("id")): x for x in previous.get("letters") or []}
        cur_letters = {str(x.get("id")): x for x in current.get("letters") or []}
        for item_id in cur_letters.keys() - prev_letters.keys():
            item = cur_letters[item_id]
            self._fire(
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

        prev_packages = {self._identity(x): x for x in previous.get("packages") or [] if self._identity(x)}
        cur_packages = {self._identity(x): x for x in current.get("packages") or [] if self._identity(x)}

        for key, new in cur_packages.items():
            old = prev_packages.get(key)
            # Historical delivered shipments can re-appear in PostNL's account feed.
            # They are never "new"; only a real active -> delivered transition counts.
            if old is None and new.get("delivered"):
                _LOGGER.debug("Suppressed historical delivered parcel %s", key)
                continue
            data = self._package_event_data(new)
            if old is None:
                self._fire(EVENT_NEW_PACKAGE, data)
            if not new.get("delivered") and self._has_window(new) and not (old and not old.get("delivered") and self._has_window(old)):
                self._fire(EVENT_DELIVERY_WINDOW_KNOWN, data)
            if old is None or (old.get("delivered") and new.get("delivered")):
                continue
            self._fire_changes(old, new, data)

        # A parcel can vanish from the account list right after delivery. Re-check it once
        # via Track & Trace so the final status ("Bezorgd") still produces events.
        for key, old in prev_packages.items():
            if key in cur_packages or old.get("delivered") or not old.get("detailsUrl"):
                continue
            try:
                refreshed = await self.api.refresh_package_tracking(old)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Final PostNL status refresh failed for %s: %s", key, err)
                continue
            if self._fingerprint(old) != self._fingerprint(refreshed):
                self._fire_changes(old, refreshed, self._package_event_data(refreshed))

    def _fire_changes(self, old: dict[str, Any], new: dict[str, Any], data: dict[str, Any]) -> None:
        old_window = old.get("deliveryWindow") or ""
        new_window = new.get("deliveryWindow") or ""
        if old_window and new_window and old_window != new_window and not new.get("delivered"):
            self._fire(EVENT_DELIVERY_WINDOW_CHANGED, {**data, "old_delivery_window": old_window})
        old_event, new_event = self._event_text(old), self._event_text(new)
        if new_event and new_event != old_event:
            self._fire(EVENT_PACKAGE_EVENT_CHANGED, {**data, "old_event": old_event})
        if not str(old.get("weight") or "").strip() and str(new.get("weight") or "").strip():
            self._fire(EVENT_PACKAGE_WEIGHT_KNOWN, data)
        if not str(old.get("dimensions") or "").strip() and str(new.get("dimensions") or "").strip():
            self._fire(EVENT_PACKAGE_DIMENSIONS_KNOWN, data)
        if not old.get("delivered") and new.get("delivered"):
            self._fire(EVENT_PACKAGE_DELIVERED, data)
        if self._fingerprint(old) != self._fingerprint(new):
            self._fire(
                EVENT_PACKAGE_STATUS_CHANGED,
                {**data, "old_status": str(old.get("statusRaw") or old.get("status") or "")},
            )

    def _package_event_data(self, p: dict[str, Any]) -> dict[str, Any]:
        return {
            "entry_id": self.entry.entry_id,
            "id": p.get("id") or "",
            "tracking": p.get("barcode") or "",
            "sender": p.get("sender") or "",
            "receiver": p.get("receiver") or "",
            "status": p.get("statusRaw") or p.get("status") or "",
            "status_code": p.get("statusCode") or "",
            "canonical_status": p.get("canonicalStatus") or "unknown",
            "observation_code": p.get("observationCode") or "",
            "event": p.get("latestStatusEvent") or "",
            "status_time": p.get("statusChangedAt") or "",
            "delivery_date": p.get("deliveryDate") or "",
            "delivery_window": p.get("deliveryWindow") or "",
            "delivery_window_from": p.get("deliveryWindowFrom") or "",
            "delivery_window_to": p.get("deliveryWindowTo") or "",
            "delivered": bool(p.get("delivered")),
            "shipment_type": p.get("shipmentType") or "",
            "delivery_address_type": p.get("deliveryAddressType") or "",
            "direction": p.get("direction") or "",
            "shared_from": p.get("sourceDisplayName") or "",
            "details_url": p.get("detailsUrl") or "",
            "weight": p.get("weight") or "",
            "weight_kg": p.get("weightKg"),
            "dimensions": p.get("dimensions") or "",
            "length_cm": p.get("dimensionLengthCm"),
            "width_cm": p.get("dimensionWidthCm"),
            "height_cm": p.get("dimensionHeightCm"),
            "pickup": bool(p.get("pickup")),
            "pickup_point": p.get("pickupPoint") or "",
        }
