"""Update platform for HA Portainer Link."""

from __future__ import annotations

try:
    from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
except ImportError:
    from homeassistant.components.update import UpdateEntity

    UpdateEntityFeature = None
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory

from .const import DATA_COORDINATOR, DOMAIN
from .entity import BaseContainerEntity, container_name


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up Portainer update entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    if not coordinator.is_update_sensors_enabled():
        return

    entities = [
        ContainerUpdateEntity(
            coordinator,
            entry.entry_id,
            container_id,
            container_name(container),
            coordinator.get_container_stack_info(container_id) or {},
        )
        for container_id, container in coordinator.containers.items()
    ]
    async_add_entities(entities)


class ContainerUpdateEntity(BaseContainerEntity, UpdateEntity):
    """Native update entity for a Docker container image."""

    entity_suffix = "update"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_supported_features = UpdateEntityFeature.INSTALL if UpdateEntityFeature else 1

    def __init__(self, coordinator, entry_id, container_id, name, stack_info) -> None:
        super().__init__(coordinator, entry_id, container_id, name, stack_info)
        self._attr_name = f"{name} Update"
        self._attr_in_progress = False

    @property
    def installed_version(self):
        data = self._image_data
        if self.coordinator.get_update_availability(self.current_container_id):
            return data.get("current_digest") or data.get("current_version")
        return data.get("current_version") or data.get("current_digest")

    @property
    def latest_version(self):
        data = self._image_data
        if self.coordinator.get_update_availability(self.current_container_id):
            return data.get("available_digest") or data.get("available_version")
        return self.installed_version

    @property
    def release_summary(self):
        data = self._image_data
        current_digest = data.get("current_digest")
        available_digest = data.get("available_digest")
        if current_digest and available_digest:
            return f"Current digest: {current_digest}; available digest: {available_digest}"
        return None

    @property
    def _image_data(self) -> dict:
        container_id = self.current_container_id
        return self.coordinator.image_data.get(container_id or "", {})

    @property
    def available(self) -> bool:
        return super().available and bool(self._image_data)

    @property
    def is_on(self) -> bool:
        return self.coordinator.get_update_availability(self.current_container_id)

    async def async_install(self, version: str | None, backup: bool, **kwargs) -> None:
        """Pull the latest image and recreate the container with it."""
        container_id = self.current_container_id
        if not container_id:
            raise HomeAssistantError(f"Container {self.container_name} is not available")
        self._attr_in_progress = True
        self.async_write_ha_state()
        try:
            result = await self.coordinator.api.recreate_container(self.endpoint_id, container_id, pull_image=True)
        finally:
            self._attr_in_progress = False
            self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
        if result is None:
            raise HomeAssistantError(
                "This Portainer version cannot recreate containers via the API (requires Portainer 2.19+). "
                "Pull the image and recreate the container in Portainer."
            )
        if not result:
            raise HomeAssistantError(f"Failed to update container {self.container_name}; see the log for details")
