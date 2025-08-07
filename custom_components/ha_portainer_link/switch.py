import logging
from homeassistant.components.switch import SwitchEntity
import asyncio

from .const import DOMAIN
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

    switches = []
    
    # Create switches for all containers
    for container_id, container_data in coordinator.containers.items():
        container_name = container_data.get("Names", ["unknown"])[0].strip("/")
        state = container_data.get("State", "unknown")
        
        # Get detailed stack information from coordinator's processed data
        stack_info = coordinator.get_container_stack_info(container_id) or {
            "stack_name": None,
            "service_name": None,
            "container_number": None,
            "is_stack_container": False
        }
        
        _LOGGER.debug("🔍 Processing container: %s (ID: %s, State: %s, Stack: %s)", container_name, container_id, state, stack_info.get("stack_name"))
        
        # Create switch for this container
        switches.append(ContainerSwitch(coordinator, entry_id, container_id, container_name, state, stack_info))

    _LOGGER.info("✅ Created %d switch entities", len(switches))
    async_add_entities(switches, update_before_add=True)

class ContainerSwitch(BaseContainerEntity, SwitchEntity):
    """Switch to start/stop a Docker container."""

    def __init__(self, coordinator, entry_id, container_id, container_name, state, stack_info):
        """Initialize the container switch."""
        super().__init__(coordinator, entry_id, container_id, container_name, stack_info)
        self._available = True

    @property
    def entity_type(self) -> str:
        return "switch"

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        display_name = self._get_container_name_display()
        return f"Power {display_name}"

    @property
    def is_on(self) -> bool:
        """Return True if the switch is on."""
        container_data = self._get_container_data()
        if container_data:
            is_running = container_data.get("State") == "running"
            _LOGGER.debug("🔍 Switch %s state: %s (running: %s)", self.name, container_data.get("State"), is_running)
            return is_running
        _LOGGER.debug("🔍 Switch %s: no container data available", self.name)
        return False

    @property
    def available(self) -> bool:
        """Return True if the switch is available."""
        return self._available

    @property
    def icon(self) -> str:
        """Return the icon of the switch."""
        return "mdi:power"

    async def async_turn_on(self, **kwargs):
        """Start the Docker container."""
        try:
            success = await self.coordinator.api.start_container(self.coordinator.endpoint_id, self.container_id)
            if success:
                self._available = True
                # Trigger coordinator refresh to update all entities
                await self.coordinator.async_request_refresh()
                # Small delay to ensure data is updated
                await asyncio.sleep(1)
            else:
                self._available = False
        except Exception as e:
            _LOGGER.error("Failed to start container %s: %s", self.container_name, e)
            self._available = False

    async def async_turn_off(self, **kwargs):
        """Stop the Docker container."""
        try:
            success = await self.coordinator.api.stop_container(self.coordinator.endpoint_id, self.container_id)
            if success:
                self._available = True
                # Trigger coordinator refresh to update all entities
                await self.coordinator.async_request_refresh()
                # Small delay to ensure data is updated
                await asyncio.sleep(1)
            else:
                self._available = False
        except Exception as e:
            _LOGGER.error("Failed to stop container %s: %s", self.container_name, e)
            self._available = False
