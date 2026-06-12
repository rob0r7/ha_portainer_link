"""Switch platform for HA Portainer Link."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity

from .const import DATA_COORDINATOR, DOMAIN
from .entity import BaseContainerEntity, container_name, is_container_running


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up Portainer switches."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    entities = [
        ContainerSwitch(
            coordinator,
            entry.entry_id,
            container_id,
            container_name(container),
            coordinator.get_container_stack_info(container_id) or {},
        )
        for container_id, container in coordinator.containers.items()
    ]
    async_add_entities(entities)


class ContainerSwitch(BaseContainerEntity, SwitchEntity):
    """Switch to start and stop a Docker container."""

    entity_suffix = "switch"
    _attr_icon = "mdi:power"

    def __init__(self, coordinator, entry_id, container_id, name, stack_info) -> None:
        super().__init__(coordinator, entry_id, container_id, name, stack_info)
        self._attr_name = f"{name} Switch"

    @property
    def is_on(self) -> bool:
        return is_container_running(self.container)

    async def async_turn_on(self, **kwargs) -> None:
        container_id = self.current_container_id
        if container_id:
            await self.coordinator.api.start_container(self.endpoint_id, container_id)
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        container_id = self.current_container_id
        if container_id:
            await self.coordinator.api.stop_container(self.endpoint_id, container_id)
            await self.coordinator.async_request_refresh()
