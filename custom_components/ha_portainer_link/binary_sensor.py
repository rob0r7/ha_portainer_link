import logging
from homeassistant.components.binary_sensor import BinarySensorEntity

from .const import DOMAIN
from .entity import BaseContainerEntity
from .coordinator import PortainerDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
_LOGGER.info("Loaded Portainer binary sensor integration.")

async def async_setup_entry(hass, entry, async_add_entities):
    config = entry.data
    endpoint_id = config["endpoint_id"]
    entry_id = entry.entry_id

    _LOGGER.info("🚀 Setting up HA Portainer Link binary sensors for entry %s (endpoint %s)", entry_id, endpoint_id)
    
    # Get coordinator
    coordinator = hass.data[DOMAIN][f"{entry_id}_coordinator"]
    
    # Wait for initial data
    await coordinator.async_config_entry_first_refresh()

    entities = []
    
    # Create binary sensors for all containers
    for container_id, container_data in coordinator.containers.items():
        container_name = container_data.get("Names", ["unknown"])[0].strip("/")
        
        # Get stack information
        stack_info = coordinator.get_container_stack_info(container_data)
        
        _LOGGER.debug("🔍 Processing container: %s (ID: %s)", container_name, container_id)
        
        # Create binary sensor for this container
        entities.append(ContainerUpdateAvailableSensor(coordinator, entry_id, container_id, container_name, stack_info))

    _LOGGER.info("✅ Created %d binary sensor entities", len(entities))
    async_add_entities(entities, update_before_add=True)

class ContainerUpdateAvailableSensor(BaseContainerEntity, BinarySensorEntity):
    """Binary sensor representing if a container has updates available."""

    @property
    def entity_type(self) -> str:
        return "update_available"

    @property
    def name(self) -> str:
        """Return the name of the binary sensor."""
        display_name = self._get_container_name_display()
        return f"Update {display_name}"

    @property
    def is_on(self) -> bool:
        """Return True if the binary sensor is on."""
        return getattr(self, '_attr_is_on', False)

    @property
    def icon(self):
        """Return the icon of the binary sensor."""
        return "mdi:update" if self.is_on else "mdi:update-disabled"

    async def async_update(self):
        """Update the update availability status."""
        try:
            has_update = await self.coordinator.api.check_image_updates(self.coordinator.endpoint_id, self.container_id)
            self._attr_is_on = has_update
        except Exception as e:
            _LOGGER.warning("Failed to check update availability for %s: %s", self.name, e)
