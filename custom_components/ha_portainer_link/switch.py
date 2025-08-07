import logging
from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN, CONF_ENABLE_CONTAINER_BUTTONS, DEFAULT_ENABLE_CONTAINER_BUTTONS
from .entity import BaseContainerEntity
from .coordinator import PortainerDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
_LOGGER.info("Loaded Portainer switch integration.")

async def async_setup_entry(hass, entry, async_add_entities):
    config = entry.data
    endpoint_id = config["endpoint_id"]
    entry_id = entry.entry_id

    _LOGGER.info("🚀 Setting up HA Portainer Link switches for entry %s (endpoint %s)", entry_id, endpoint_id)
    
    # Get coordinator
    coordinator = hass.data[DOMAIN][f"{entry_id}_coordinator"]
    
    # Wait for initial data
    await coordinator.async_config_entry_first_refresh()

    entities = []
    
    # Check if container buttons are enabled
    container_buttons_enabled = config.get(CONF_ENABLE_CONTAINER_BUTTONS, DEFAULT_ENABLE_CONTAINER_BUTTONS)
    
    _LOGGER.info("📊 Switch configuration: Container buttons=%s", container_buttons_enabled)
    
    # Create switches for all containers
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
        
        # Create container switches only if enabled
        if container_buttons_enabled:
            entities.append(ContainerSwitch(coordinator, entry_id, container_id, container_name, stack_info))

    _LOGGER.info("✅ Created %d switch entities (Container buttons: %s)", 
                 len(entities), container_buttons_enabled)
    async_add_entities(entities, update_before_add=True)

class ContainerSwitch(BaseContainerEntity, SwitchEntity):
    """Switch for container start/stop."""

    @property
    def entity_type(self) -> str:
        return "container_switch"

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        display_name = self._get_container_name_display()
        return f"Switch {display_name}"

    @property
    def is_on(self):
        """Return true if the switch is on."""
        container_data = self._get_container_data()
        if container_data:
            state = container_data.get("State", {})
            return state.get("Running", False)
        return False

    @property
    def icon(self):
        """Return the icon of the switch."""
        return "mdi:docker" if self.is_on else "mdi:docker-outline"

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        try:
            _LOGGER.info("🔄 Starting container %s", self.container_id)
            await self.coordinator.api.start_container(self.coordinator.endpoint_id, self.container_id)
            
            # Trigger a refresh to update the state
            await self.coordinator.async_request_refresh()
            
            # Small delay to allow the state to propagate
            import asyncio
            await asyncio.sleep(1)
            
            _LOGGER.debug("✅ Container %s started successfully", self.container_id)
            
        except Exception as e:
            _LOGGER.error("❌ Error starting container %s: %s", self.container_id, e)
            raise

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        try:
            _LOGGER.info("🔄 Stopping container %s", self.container_id)
            await self.coordinator.api.stop_container(self.coordinator.endpoint_id, self.container_id)
            
            # Trigger a refresh to update the state
            await self.coordinator.async_request_refresh()
            
            # Small delay to allow the state to propagate
            import asyncio
            await asyncio.sleep(1)
            
            _LOGGER.debug("✅ Container %s stopped successfully", self.container_id)
            
        except Exception as e:
            _LOGGER.error("❌ Error stopping container %s: %s", self.container_id, e)
            raise
