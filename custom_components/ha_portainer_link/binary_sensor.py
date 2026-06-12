"""Binary sensor platform for HA Portainer Link."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .entity import BaseContainerEntity, container_name


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up Portainer binary sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    if not coordinator.is_update_sensors_enabled():
        return

    entities = [
        ContainerUpdateAvailableSensor(
            coordinator,
            entry.entry_id,
            container_id,
            container_name(container),
            coordinator.get_container_stack_info(container_id) or {},
        )
        for container_id, container in coordinator.containers.items()
    ]
    async_add_entities(entities)


class ContainerUpdateAvailableSensor(BaseContainerEntity, BinarySensorEntity):
    """Binary sensor representing whether a container image update is available."""

    entity_suffix = "update_available"
    _attr_icon = "mdi:update"

    def __init__(self, coordinator, entry_id, container_id, name, stack_info) -> None:
        super().__init__(coordinator, entry_id, container_id, name, stack_info)
        self._attr_name = f"{name} Update Available"

    @property
    def is_on(self) -> bool:
        return self.coordinator.get_update_availability(self.current_container_id)
