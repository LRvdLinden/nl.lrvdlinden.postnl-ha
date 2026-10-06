"""Manual refresh button."""
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PostNLCoordinator
from .entity import PostNLEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([PostNLRefreshButton(entry.runtime_data)])


class PostNLRefreshButton(PostNLEntity, ButtonEntity):
    _attr_name = "Vernieuwen"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: PostNLCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_refresh"

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()
