import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import EntityCategory
from typing import Optional, Dict, Any

from .const import DOMAIN
from .entity import BaseContainerEntity
from .coordinator import PortainerDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Portainer switches from a config entry."""
    config = dict(entry.data)  # Create mutable copy
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
    
    # Container switches are always available as core functionality
    _LOGGER.info("📊 Switch configuration: Container switches are always enabled (core functionality)")
    
    # Coordinator data is already loaded in main setup
    entities = []

    # Keep track of created switches to avoid duplicates
    created_for: set[str] = set()

    def _create_switch(container_id: str, container_data: dict) -> list:
        container_name = container_data.get("Names", ["unknown"])[0].strip("/")
        # Get detailed stack information from coordinator's processed data
        stack_info = coordinator.get_container_stack_info(container_id) or {
            "stack_name": None,
            "service_name": None,
            "container_number": None,
            "is_stack_container": False
        }
        _LOGGER.debug("🔍 Processing container: %s (ID: %s, Stack: %s)", 
                     container_name, container_id, stack_info.get("stack_name"))
        return [ContainerSwitch(coordinator, entry_id, container_id, container_name, stack_info)]
    
    # Initial creation for all containers
    for container_id, container_data in coordinator.containers.items():
        entities.extend(_create_switch(container_id, container_data))
        created_for.add(container_id)

    _LOGGER.info("✅ Created %d switch entities", len(entities))
    
    # Debug: Log all created entities
    for entity in entities:
        _LOGGER.debug("📋 Switch entity: %s (unique_id: %s)", entity.name, entity.unique_id)
    
    async_add_entities(entities, update_before_add=False)

    # Dynamic addition when new containers are discovered
    def _add_new_switches() -> None:
        new_entities: list = []
        for container_id, container_data in coordinator.containers.items():
            if container_id not in created_for:
                _LOGGER.info("➕ Discovered new container %s, creating switch", container_id)
                new_entities.extend(_create_switch(container_id, container_data))
                created_for.add(container_id)
        if new_entities:
            async_add_entities(new_entities, update_before_add=False)

    coordinator.async_add_listener(_add_new_switches)


class ContainerSwitch(BaseContainerEntity, SwitchEntity):
    """Representation of a Portainer container switch."""

    @property
    def entity_type(self) -> str:
        """Return the entity type."""
        return "switch"

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        container_name = self._get_container_name_display()
        return f"Container Switch {container_name}"

    def _get_container_data(self) -> Optional[Dict[str, Any]]:
        """Get container data from coordinator."""
        try:
            container_data = self.coordinator.get_container(self.container_id)
            if not container_data:
                _LOGGER.warning("⚠️ Container data not found for ID: %s", self.container_id)
                return None
            
            # Debug: Log container state
            container_state = container_data.get("State", {})
            _LOGGER.debug("🔍 Container %s state: %s (type: %s)", 
                         self.container_id, container_state, type(container_state))
            
            return container_data
        except Exception as e:
            _LOGGER.error("❌ Error getting container data for %s: %s", self.container_id, e)
            return None

    @property
    def is_on(self):
        """Return true if the container is running."""
        try:
            container_data = self._get_container_data()
            if not container_data:
                _LOGGER.warning("⚠️ No container data available for %s", self.container_id)
                return False
            
            # Handle different state formats
            container_state = container_data.get("State", {})
            
            if isinstance(container_state, dict):
                # Standard format: {"Running": true, "Status": "running"}
                is_running = container_state.get("Running", False)
                _LOGGER.debug("🔍 Container %s Running state: %s", self.container_id, is_running)
                return bool(is_running)
            elif isinstance(container_state, str):
                # String format: "running", "exited", etc.
                is_running = container_state.lower() == "running"
                _LOGGER.debug("🔍 Container %s string state: %s (running: %s)", 
                             self.container_id, container_state, is_running)
                return is_running
            else:
                _LOGGER.warning("⚠️ Unknown container state format for %s: %s (type: %s)", 
                               self.container_id, container_state, type(container_state))
                return False
                
        except Exception as e:
            _LOGGER.error("❌ Error checking container state for %s: %s", self.container_id, e)
            return False

    @property
    def icon(self):
        """Return the icon of the switch."""
        return "mdi:docker" if self.is_on else "mdi:docker-outline"

    @property
    def device_class(self):
        """Return the device class of the switch."""
        from homeassistant.components.switch import SwitchDeviceClass
        return SwitchDeviceClass.SWITCH

    @property
    def entity_category(self):
        """Return the entity category."""
        return EntityCategory.CONFIG

    async def async_turn_on(self, **kwargs):
        """Turn the container on (start it)."""
        try:
            _LOGGER.info("▶️ Starting container %s", self.container_id)
            
            success = await self.coordinator.api.start_container(
                self.coordinator.endpoint_id, 
                self.container_id
            )
            
            if success:
                _LOGGER.info("✅ Successfully started container %s", self.container_id)
                # Force immediate state update
                self.async_write_ha_state()
                # Request coordinator refresh
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error("❌ Failed to start container %s", self.container_id)
                
        except Exception as e:
            _LOGGER.exception("❌ Error starting container %s: %s", self.container_id, e)

    async def async_turn_off(self, **kwargs):
        """Turn the container off (stop it)."""
        try:
            _LOGGER.info("🛑 Stopping container %s", self.container_id)
            
            success = await self.coordinator.api.stop_container(
                self.coordinator.endpoint_id, 
                self.container_id
            )
            
            if success:
                _LOGGER.info("✅ Successfully stopped container %s", self.container_id)
                # Force immediate state update
                self.async_write_ha_state()
                # Request coordinator refresh
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error("❌ Failed to stop container %s", self.container_id)
                
        except Exception as e:
            _LOGGER.exception("❌ Error stopping container %s: %s", self.container_id, e)
