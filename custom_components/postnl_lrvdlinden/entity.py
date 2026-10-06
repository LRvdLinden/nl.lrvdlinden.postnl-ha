"""Shared PostNL entity base."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PostNLCoordinator


class PostNLEntity(CoordinatorEntity[PostNLCoordinator]):
    """Base entity tied to the PostNL account."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PostNLCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name="Mijn PostNL",
            manufacturer="PostNL",
            model="PostNL account",
            sw_version="0.1.0",
        )
