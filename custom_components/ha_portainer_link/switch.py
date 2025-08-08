import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import EntityCategory
from typing import Optional, Dict, Any

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
    
    # Debug configuration
    _LOGGER.info("🔧 Configuration debug:")
    _LOGGER.info("  - Integration mode: %s", config.get("integration_mode", "not set"))
    _LOGGER.info("  - Container buttons enabled: %s", coordinator.is_container_buttons_enabled())
    _LOGGER.info("  - Stack view enabled: %s", coordinator.is_stack_view_enabled())
    _LOGGER.info("  - Update interval: %s minutes", config.get("update_interval", "not set"))
    
    # Wait for initial data
    await coordinator.async_config_entry_first_refresh()

    entities = []
    
    # Container switches are always available as core functionality
    _LOGGER.info("📊 Switch configuration: Container switches are always enabled (core functionality)")
    
    # Debug: Check if we have containers
    container_count = len(coordinator.containers)
    _LOGGER.info("🔍 Found %d containers in coordinator", container_count)
    
    # Force create at least one switch even if no containers found
    if container_count == 0:
        _LOGGER.warning("⚠️ No containers found in coordinator. Creating test switch only.")
        test_switch = TestSwitch(coordinator, entry_id)
        entities.append(test_switch)
        _LOGGER.info("🧪 Added test switch for debugging (no containers found)")
        async_add_entities(entities, update_before_add=True)
        return
    
    # Create switches for all containers
    for container_id, container_data in coordinator.containers.items():
        container_name = container_data.get("Names", ["unknown"])[0].strip("/")
        
        # Fix: Ensure container_state is a dictionary, not a string
        container_state = container_data.get("State", {})
        if isinstance(container_state, dict):
            is_running = container_state.get("Running", False)
        else:
            _LOGGER.warning("⚠️ Container state is not a dictionary for %s: %s", container_name, type(container_state))
            is_running = False
        
        # Get detailed stack information from coordinator's processed data
        stack_info = coordinator.get_container_stack_info(container_id) or {
            "stack_name": None,
            "service_name": None,
            "container_number": None,
            "is_stack_container": False
        }
        
        _LOGGER.debug("🔍 Processing container: %s (ID: %s, Stack: %s, Running: %s, State: %s)", 
                     container_name, container_id, stack_info.get("stack_name"), is_running, container_state)
        
        # Always create container switches (core functionality)
        switch_entity = ContainerSwitch(coordinator, entry_id, container_id, container_name, stack_info)
        entities.append(switch_entity)
        
        _LOGGER.debug("✅ Created switch for container: %s (ID: %s)", container_name, container_id)

    _LOGGER.info("✅ Created %d switch entities (Container switches: always enabled)", len(entities))
    
    # Debug: Log all created entities
    for entity in entities:
        _LOGGER.debug("📋 Switch entity: %s (unique_id: %s)", entity.name, entity.unique_id)
    
    # Add a test switch for debugging
    test_switch = TestSwitch(coordinator, entry_id)
    entities.append(test_switch)
    _LOGGER.info("🧪 Added test switch for debugging")
    
    # Add a simple always-on switch for testing
    simple_switch = SimpleTestSwitch(entry_id)
    entities.append(simple_switch)
    _LOGGER.info("🧪 Added simple test switch for debugging")
    
    # Force add entities even if empty
    if not entities:
        _LOGGER.warning("⚠️ No entities created, adding fallback test switch")
        fallback_switch = FallbackSwitch(entry_id)
        entities.append(fallback_switch)
    
    _LOGGER.info("🎯 Final entity count: %d", len(entities))
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
        # Make the name more explicit and easier to find
        if self.stack_info.get("is_stack_container"):
            return f"Container Switch {display_name}"
        else:
            return f"Portainer Switch {display_name}"

    def _get_container_data(self) -> Optional[Dict[str, Any]]:
        """Get current container data from coordinator."""
        container_data = self.coordinator.get_container(self.container_id)
        if container_data:
            _LOGGER.debug("✅ Found container data for %s (ID: %s)", self.container_name, self.container_id)
        else:
            _LOGGER.warning("⚠️ No container data found for %s (ID: %s) - Available IDs: %s", 
                           self.container_name, self.container_id,
                           list(self.coordinator.containers.keys()) if self.coordinator.containers else "None")
            
            # Try to find by name as fallback
            for cid, cdata in self.coordinator.containers.items():
                names = cdata.get("Names", [])
                if names and self.container_name in names[0]:
                    _LOGGER.info("🔄 Found container by name: %s (ID: %s) - updating container ID", 
                                self.container_name, cid)
                    self.container_id = cid
                    container_data = cdata
                    break
        
        return container_data

    @property
    def is_on(self):
        """Return true if the switch is on."""
        container_data = self._get_container_data()
        if container_data:
            # Debug: Log the full container data structure
            _LOGGER.debug("🔍 Full container data for %s: %s", self.container_name, container_data)
            
            state = container_data.get("State", {})
            # Fix: Ensure state is a dictionary, not a string
            if isinstance(state, dict):
                is_running = state.get("Running", False)
                _LOGGER.debug("🔍 Container %s state: Running=%s, State=%s, ContainerID=%s", 
                             self.container_name, is_running, state, self.container_id)
                return is_running
            else:
                _LOGGER.warning("⚠️ Container state is not a dictionary for %s: %s (type: %s)", 
                               self.container_name, state, type(state))
                # Try to extract running state from string if possible
                if isinstance(state, str):
                    is_running = "running" in state.lower()
                    _LOGGER.info("🔄 Extracted running state from string: %s -> %s", state, is_running)
                    return is_running
                return False
        else:
            _LOGGER.warning("⚠️ No container data found for %s (ID: %s) - Available containers: %s", 
                           self.container_name, self.container_id, 
                           list(self.coordinator.containers.keys()) if self.coordinator.containers else "None")
            return False

    @property
    def icon(self):
        """Return the icon of the switch."""
        return "mdi:docker" if self.is_on else "mdi:docker-outline"

    @property
    def device_class(self):
        """Return the device class."""
        return "switch"

    @property
    def entity_category(self):
        """Return the entity category."""
        return EntityCategory.CONFIG

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
            
            # Force update the entity state
            self.async_write_ha_state()
            
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
            
            # Force update the entity state
            self.async_write_ha_state()
            
            _LOGGER.debug("✅ Container %s stopped successfully", self.container_id)
            
        except Exception as e:
            _LOGGER.error("❌ Error stopping container %s: %s", self.container_id, e)
            raise

class TestSwitch(SwitchEntity):
    """Test switch for debugging."""
    
    def __init__(self, coordinator, entry_id):
        self.coordinator = coordinator
        self.entry_id = entry_id
        self._attr_unique_id = f"test_switch_{entry_id}"
        self._attr_name = f"Portainer Test Switch {entry_id}"
        self._attr_icon = "mdi:test-tube"
        self._attr_device_class = "switch"
        self._attr_should_poll = False
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool:
        return len(self.coordinator.containers) > 0

    async def async_turn_on(self, **kwargs):
        _LOGGER.info("🧪 Test switch turned ON - containers found: %d", len(self.coordinator.containers))

    async def async_turn_off(self, **kwargs):
        _LOGGER.info("🧪 Test switch turned OFF - containers found: %d", len(self.coordinator.containers))

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

class SimpleTestSwitch(SwitchEntity):
    """Simple test switch for debugging."""
    
    def __init__(self, entry_id):
        self.entry_id = entry_id
        self._attr_unique_id = f"simple_test_switch_{entry_id}"
        self._attr_name = f"Portainer Simple Test Switch {entry_id}"
        self._attr_icon = "mdi:test-tube"
        self._attr_device_class = "switch"
        self._attr_should_poll = False
        self._attr_available = True
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self) -> bool:
        return True

    async def async_turn_on(self, **kwargs):
        _LOGGER.info("🧪 Simple test switch turned ON - always on")

    async def async_turn_off(self, **kwargs):
        _LOGGER.info("🧪 Simple test switch turned OFF - always on")

class FallbackSwitch(SwitchEntity):
    """Fallback switch for debugging when no containers are found."""
    
    def __init__(self, entry_id):
        self.entry_id = entry_id
        self._attr_unique_id = f"fallback_switch_{entry_id}"
        self._attr_name = f"Portainer Fallback Switch {entry_id}"
        self._attr_icon = "mdi:alert-circle"
        self._attr_device_class = "switch"
        self._attr_should_poll = False
        self._attr_available = True
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self) -> bool:
        return False

    async def async_turn_on(self, **kwargs):
        _LOGGER.info("🧪 Fallback switch turned ON - this indicates no containers were found")

    async def async_turn_off(self, **kwargs):
        _LOGGER.info("🧪 Fallback switch turned OFF - this indicates no containers were found")
