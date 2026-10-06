"""PostNL binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PostNLCoordinator
from .entity import PostNLEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: PostNLCoordinator = entry.runtime_data
    async_add_entities([
        PostNLBinarySensor(coordinator, "mail_expected", "Post verwacht", "mdi:email-fast-outline", lambda c: bool((c.data or {}).get("letters"))),
        PostNLBinarySensor(coordinator, "package_delivered", "Pakket bezorgd", "mdi:package-variant-closed-check", _latest_package_delivered),
        PostNLBinarySensor(coordinator, "connected", "Verbonden", "mdi:cloud-check-outline", lambda c: bool(c.last_update_success)),
    ])


def _latest_package_delivered(coordinator: PostNLCoordinator) -> bool:
    """Return whether the most recently updated package is delivered."""
    packages = list((coordinator.data or {}).get("packages") or [])
    packages.sort(
        key=lambda package: package.get("statusChangedAt")
        or package.get("deliveredTimeStamp")
        or package.get("deliveryDate")
        or package.get("createdAt")
        or "",
        reverse=True,
    )
    return bool(packages and packages[0].get("delivered"))


class PostNLBinarySensor(PostNLEntity, BinarySensorEntity):
    def __init__(self, coordinator: PostNLCoordinator, key: str, name: str, icon: str, fn) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._fn = fn

    @property
    def is_on(self) -> bool:
        return bool(self._fn(self.coordinator))
