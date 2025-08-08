import logging
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, CONF_ENABLE_UPDATE_SENSORS, DEFAULT_ENABLE_UPDATE_SENSORS
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
    
    # Check if update sensors are enabled
    update_sensors_enabled = config.get(CONF_ENABLE_UPDATE_SENSORS, DEFAULT_ENABLE_UPDATE_SENSORS)
    
    _LOGGER.info("📊 Binary sensor configuration: Update sensors=%s", update_sensors_enabled)
    
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
        
        # Create update sensors only if enabled
        if update_sensors_enabled:
            entities.append(ContainerUpdateAvailableSensor(coordinator, entry_id, container_id, container_name, stack_info))

    _LOGGER.info("✅ Created %d binary sensor entities (Update sensors: %s)", 
                 len(entities), update_sensors_enabled)
    async_add_entities(entities, update_before_add=True)

class ContainerUpdateAvailableSensor(BaseContainerEntity, BinarySensorEntity):
    """Binary sensor for container update availability."""

    @property
    def entity_type(self) -> str:
        return "update_available"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        display_name = self._get_container_name_display()
        return f"Update Available {display_name}"

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        # This will be updated by the coordinator
        return getattr(self, '_state', False)

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:update" if self.is_on else "mdi:update-disabled"

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.CONFIG

    async def async_update(self):
        """Update the sensor."""
        try:
            container_data = self._get_container_data()
            if not container_data:
                self._state = False
                return

            # Check if updates are available for this container
            has_updates = await self.coordinator.api.check_image_updates(
                self.coordinator.endpoint_id, self.container_id
            )
            self._state = has_updates
            
        except Exception as e:
            _LOGGER.error("❌ Error updating update sensor for container %s: %s", self.container_id, e)
            self._state = False
