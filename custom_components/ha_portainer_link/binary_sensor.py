import logging
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .entity import BaseContainerEntity
from .coordinator import PortainerDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    config = dict(entry.data)  # Create mutable copy
    endpoint_id = config["endpoint_id"]
    entry_id = entry.entry_id

    _LOGGER.info("🚀 Setting up HA Portainer Link binary sensors for entry %s (endpoint %s)", entry_id, endpoint_id)
    
    # Get coordinator
    coordinator = hass.data[DOMAIN][f"{entry_id}_coordinator"]
    
    # Check if update sensors are enabled using coordinator
    update_sensors_enabled = coordinator.is_update_sensors_enabled()
    
    _LOGGER.info("📊 Binary sensor configuration: Update sensors=%s", update_sensors_enabled)
    
    # If update sensors are disabled, don't create any entities
    if not update_sensors_enabled:
        _LOGGER.info("✅ No binary sensors to create (update sensors disabled)")
        return
    
    # Coordinator data is already loaded in main setup
    entities = []
    
    # Create binary sensors for all containers
    for container_id, container_data in coordinator.containers.items():
        container_name = container_data.get("Names", ["unknown"])[0].strip("/")
        
        # Get detailed stack information from coordinator's processed data
        stack_info = coordinator.get_container_stack_info(container_id) or {
            "stack_name": None,
            "service_name": None,
            "container_number": None,
            "is_stack_container": False
        }
        
        _LOGGER.debug("🔍 Processing container: %s (ID: %s, Stack: %s)", container_name, container_id, stack_info.get("stack_name"))
        
        entities.append(ContainerUpdateAvailableSensor(coordinator, entry_id, container_id, container_name, stack_info))

    _LOGGER.info("✅ Created %d binary sensor entities", len(entities))
    async_add_entities(entities, update_before_add=True)

class ContainerUpdateAvailableSensor(BaseContainerEntity, BinarySensorEntity):
    """Binary sensor for container update availability."""

    @property
    def entity_type(self) -> str:
        return "update_available"

    @property
    def name(self) -> str:
        display_name = self._get_container_name_display()
        return f"Update Available {display_name}"

    @property
    def is_on(self):
        """Return true if updates are available for this container."""
        return bool(self.coordinator.get_update_availability(self.container_id))

    @property
    def icon(self):
        return "mdi:update" if self.is_on else "mdi:update-disabled"

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.DIAGNOSTIC
