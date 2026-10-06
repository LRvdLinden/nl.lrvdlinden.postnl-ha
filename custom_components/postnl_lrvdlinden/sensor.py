"""PostNL sensors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PostNLCoordinator
from .entity import PostNLEntity


@dataclass(frozen=True, kw_only=True)
class PostNLSensorDescription(SensorEntityDescription):
    value_fn: Callable[[PostNLCoordinator], Any]
    attr_fn: Callable[[PostNLCoordinator], dict[str, Any]] | None = None
    role: str | None = None


def _active(c: PostNLCoordinator) -> dict[str, Any]:
    return c.active_package() or {}


def _mail_attrs(c: PostNLCoordinator) -> dict[str, Any]:
    items = []
    source = list((c.data or {}).get("letters") or [])
    source.sort(key=lambda item: item.get("deliveryDate") or "", reverse=True)
    for item in source:
        item_id = str(item.get("id") or "")
        items.append(
            {
                "id": item_id,
                "title": item.get("title") or "",
                "sender": item.get("sender") or "",
                "delivery_date": item.get("deliveryDate"),
                "unread": bool(item.get("unread")),
                "image_available": item_id in c.image_cache,
            }
        )
    return {
        "postnl_role": "mail",
        "entry_id": c.entry.entry_id,
        "mail_api_status": (c.data or {}).get("mailApiStatus") or "unknown",
        "mail_api_error": (c.data or {}).get("mailApiError"),
        "items": items,
    }


def _package_attrs(c: PostNLCoordinator) -> dict[str, Any]:
    packages = []
    source = list((c.data or {}).get("packages") or [])
    source.sort(key=lambda p: p.get("deliveryDate") or p.get("deliveryWindowFrom") or p.get("createdAt") or "", reverse=True)
    for p in source:
        packages.append(
            {
                "id": p.get("id"), "tracking": p.get("barcode") or "", "sender": p.get("sender") or "",
                "receiver": p.get("receiver") or "", "status": p.get("statusRaw") or p.get("status") or "",
                "event": p.get("latestStatusEvent") or "", "status_time": p.get("statusChangedAt") or "",
                "delivery_date": p.get("deliveryDate"), "delivery_window": p.get("deliveryWindow") or "",
                "delivery_window_from": p.get("deliveryWindowFrom"), "delivery_window_to": p.get("deliveryWindowTo"),
                "delivered": bool(p.get("delivered")), "shipment_type": p.get("shipmentType") or "",
                "direction": p.get("direction") or "incoming", "created_at": p.get("createdAt"),
            }
        )
    active_raw = c.active_package()
    active = None
    if active_raw:
        active = next((x for x in packages if x.get("id") == active_raw.get("id")), None)
    return {
        "postnl_role": "packages",
        "entry_id": c.entry.entry_id,
        "items": packages,
        "active_package": active,
        "time_zone": c.hass.config.time_zone,
    }


SENSORS: tuple[PostNLSensorDescription, ...] = (
    PostNLSensorDescription(key="mail_count", translation_key="mail_count", name="Poststukken", icon="mdi:email-outline", value_fn=lambda c: len((c.data or {}).get("letters") or []), attr_fn=_mail_attrs, role="mail"),
    PostNLSensorDescription(key="package_count", translation_key="package_count", name="Pakketten", icon="mdi:package-variant-closed", value_fn=lambda c: len([p for p in ((c.data or {}).get("packages") or []) if not p.get("delivered")]), attr_fn=_package_attrs, role="packages"),
    PostNLSensorDescription(key="next_delivery", translation_key="next_delivery", name="Volgende bezorging", icon="mdi:truck-delivery-outline", value_fn=lambda c: (_active(c).get("deliveryWindow") or _active(c).get("deliveryDate") or "—")),
    PostNLSensorDescription(key="delivery_date", translation_key="delivery_date", name="Bezorgdatum", icon="mdi:calendar", value_fn=lambda c: _active(c).get("deliveryDate") or "—"),
    PostNLSensorDescription(key="delivery_window", translation_key="delivery_window", name="Bezorgvenster", icon="mdi:clock-outline", value_fn=lambda c: _active(c).get("deliveryWindow") or "—"),
    PostNLSensorDescription(key="package_status", translation_key="package_status", name="Pakketstatus", icon="mdi:progress-clock", value_fn=lambda c: _active(c).get("statusRaw") or _active(c).get("status") or "—"),
    PostNLSensorDescription(key="package_sender", translation_key="package_sender", name="Afzender", icon="mdi:account-arrow-right-outline", value_fn=lambda c: _active(c).get("sender") or "—"),
    PostNLSensorDescription(key="package_receiver", translation_key="package_receiver", name="Ontvanger", icon="mdi:account-arrow-left-outline", value_fn=lambda c: _active(c).get("receiver") or "—"),
    PostNLSensorDescription(key="package_tracking", translation_key="package_tracking", name="Tracking", icon="mdi:barcode-scan", value_fn=lambda c: _active(c).get("barcode") or "—"),
    PostNLSensorDescription(key="package_event", translation_key="package_event", name="Laatste gebeurtenis", icon="mdi:timeline-text-outline", value_fn=lambda c: _active(c).get("latestStatusEvent") or "—"),
    PostNLSensorDescription(key="package_status_time", translation_key="package_status_time", name="Statustijd", icon="mdi:clock-check-outline", value_fn=lambda c: _active(c).get("statusChangedAt") or "—"),
    PostNLSensorDescription(key="shipment_type", translation_key="shipment_type", name="Type zending", icon="mdi:package-variant", value_fn=lambda c: _active(c).get("shipmentType") or "—"),
    PostNLSensorDescription(key="last_update", translation_key="last_update", name="Laatste update", icon="mdi:update", value_fn=lambda c: (c.data or {}).get("updatedAt") or "—"),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: PostNLCoordinator = entry.runtime_data
    async_add_entities(PostNLSensor(coordinator, description) for description in SENSORS)


class PostNLSensor(PostNLEntity, SensorEntity):
    entity_description: PostNLSensorDescription

    def __init__(self, coordinator: PostNLCoordinator, description: PostNLSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attr_fn:
            return self.entity_description.attr_fn(self.coordinator)
        return None
