import logging
from homeassistant.components.update import UpdateEntity
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .entity import BaseContainerEntity

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    config = dict(entry.data)
    endpoint_id = config["endpoint_id"]
    entry_id = entry.entry_id

    _LOGGER.info("🚀 Setting up HA Portainer Link update entities for entry %s (endpoint %s)", entry_id, endpoint_id)

    coordinator = hass.data[DOMAIN][f"{entry_id}_coordinator"]

    # Only add update entities if update sensors are enabled
    if not coordinator.is_update_sensors_enabled():
        _LOGGER.info("✅ Update entities disabled by configuration")
        return

    entities = []
    created_for: set[str] = set()

    def _create_update_entity(container_id: str, container_data: dict) -> list:
        container_name = container_data.get("Names", ["unknown"])[0].strip("/")
        stack_info = coordinator.get_container_stack_info(container_id) or {
            "stack_name": None,
            "service_name": None,
            "container_number": None,
            "is_stack_container": False,
        }
        return [ContainerUpdateEntity(coordinator, entry_id, container_id, container_name, stack_info)]

    # Initial entities
    for container_id, container_data in coordinator.containers.items():
        entities.extend(_create_update_entity(container_id, container_data))
        created_for.add(container_id)

    _LOGGER.info("✅ Created %d update entities", len(entities))
    async_add_entities(entities, update_before_add=False)

    # Dynamic add on coordinator updates
    def _add_new_update_entities() -> None:
        new_entities: list = []
        for container_id, container_data in coordinator.containers.items():
            if container_id not in created_for:
                _LOGGER.info("➕ Discovered new container %s, creating update entity", container_id)
                new_entities.extend(_create_update_entity(container_id, container_data))
                created_for.add(container_id)
        if new_entities:
            async_add_entities(new_entities, update_before_add=False)

    coordinator.async_add_listener(_add_new_update_entities)


class ContainerUpdateEntity(BaseContainerEntity, UpdateEntity):
    """Update entity representing a container's image update state."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def entity_type(self) -> str:
        return "update"

    @property
    def name(self) -> str:
        display_name = self._get_container_name_display()
        return f"Update {display_name}"

    @property
    def installed_version(self):
        data = self.coordinator.image_data.get(self.container_id, {})
        # Prefer current_version; fall back to None
        return data.get("current_version")

    @property
    def latest_version(self):
        data = self.coordinator.image_data.get(self.container_id, {})
        return data.get("available_version")

    @property
    def release_notes(self):
        return None

    @property
    def release_url(self):
        return None

    @property
    def auto_update(self):
        return False

    async def async_install(self, version: str | None, backup: bool, **kwargs) -> None:  # noqa: ARG002
        try:
            _LOGGER.info("🔄 Pulling image update for container %s", self.container_id)
            await self.coordinator.api.pull_image_update(self.coordinator.endpoint_id, self.container_id)
            # Optionally restart container to apply new image is left to user/stack update
            await self.coordinator.async_request_refresh()
        except Exception as e:
            _LOGGER.error("❌ Failed to install update for container %s: %s", self.container_id, e)

    @property
    def available(self) -> bool:
        # Available if coordinator has data for this container
        return super().available and self.container_id in self.coordinator.containers