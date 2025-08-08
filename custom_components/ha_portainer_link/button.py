import logging
import asyncio
from datetime import timedelta
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .entity import BaseContainerEntity, BaseStackEntity
from .coordinator import PortainerDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
_LOGGER.info("Loaded Portainer button integration.")

async def async_setup_entry(hass, entry, async_add_entities):
    config = dict(entry.data)  # Create mutable copy
    endpoint_id = config["endpoint_id"]
    entry_id = entry.entry_id

    _LOGGER.info("🚀 Setting up HA Portainer Link buttons for entry %s (endpoint %s)", entry_id, endpoint_id)
    
    # Get coordinator
    coordinator = hass.data[DOMAIN][f"{entry_id}_coordinator"]
    
    # Check if buttons are enabled using coordinator
    container_buttons_enabled = coordinator.is_container_buttons_enabled()
    stack_buttons_enabled = coordinator.is_stack_buttons_enabled()
    
    _LOGGER.info("📊 Button configuration: Container buttons=%s, Stack buttons=%s", 
                 container_buttons_enabled, stack_buttons_enabled)
    
    # If no buttons are enabled, don't create any entities
    if not container_buttons_enabled and not stack_buttons_enabled:
        _LOGGER.info("✅ No buttons to create (all button types disabled)")
        return
    
    # Coordinator data is already loaded in main setup
    entities = []
    
    # Create container buttons
    if container_buttons_enabled:
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
            
            # Create container buttons
            entities.append(RestartContainerButton(coordinator, entry_id, container_id, container_name, stack_info))
            entities.append(PullUpdateButton(coordinator, entry_id, container_id, container_name, stack_info))

    # Create stack buttons
    if stack_buttons_enabled and coordinator.is_stack_view_enabled():
        for stack_name, stack_data in coordinator.stacks.items():
            _LOGGER.debug("🔍 Processing stack: %s", stack_name)
            
            # Create stack buttons
            entities.append(StackStopButton(coordinator, entry_id, stack_name))
            entities.append(StackStartButton(coordinator, entry_id, stack_name))
            entities.append(StackUpdateButton(coordinator, entry_id, stack_name))

    _LOGGER.info("✅ Created %d button entities", len(entities))
    async_add_entities(entities, update_before_add=True)

class RestartContainerButton(BaseContainerEntity, ButtonEntity):
    """Button for restarting a container."""

    @property
    def entity_type(self) -> str:
        return "restart_container"

    @property
    def name(self) -> str:
        """Return the name of the button."""
        display_name = self._get_container_name_display()
        if self.stack_info.get("is_stack_container"):
            return f"Container Restart {display_name}"
        else:
            return f"Restart {display_name}"

    @property
    def icon(self):
        """Return the icon of the button."""
        return "mdi:restart"

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.CONFIG

    async def async_press(self):
        """Handle the button press."""
        try:
            _LOGGER.info("🔄 Restarting container %s", self.container_id)
            await self.coordinator.api.restart_container(self.coordinator.endpoint_id, self.container_id)
            
            # Trigger a refresh to update the state
            await self.coordinator.async_request_refresh()
            
            # Small delay to allow the state to propagate
            import asyncio
            await asyncio.sleep(1)
            
            _LOGGER.debug("✅ Container %s restarted successfully", self.container_id)
            
        except Exception as e:
            _LOGGER.error("❌ Error restarting container %s: %s", self.container_id, e)
            raise

class PullUpdateButton(BaseContainerEntity, ButtonEntity):
    """Button for pulling container updates."""

    @property
    def entity_type(self) -> str:
        return "pull_update"

    @property
    def name(self) -> str:
        """Return the name of the button."""
        display_name = self._get_container_name_display()
        if self.stack_info.get("is_stack_container"):
            return f"Container Pull Update {display_name}"
        else:
            return f"Pull Update {display_name}"

    @property
    def icon(self):
        """Return the icon of the button."""
        return "mdi:download"

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.CONFIG

    async def async_press(self):
        """Handle the button press."""
        try:
            _LOGGER.info("🔄 Pulling update for container %s", self.container_id)
            await self.coordinator.api.pull_image_update(self.coordinator.endpoint_id, self.container_id)
            
            # Trigger a refresh to update the state
            await self.coordinator.async_request_refresh()
            
            # Small delay to allow the state to propagate
            import asyncio
            await asyncio.sleep(1)
            
            _LOGGER.debug("✅ Update pulled successfully for container %s", self.container_id)
            
        except Exception as e:
            _LOGGER.error("❌ Error pulling update for container %s: %s", self.container_id, e)
            raise

class StackStopButton(BaseStackEntity, ButtonEntity):
    """Button for stopping a stack."""

    @property
    def entity_type(self) -> str:
        return "stack_stop"

    @property
    def name(self) -> str:
        """Return the name of the button."""
        return f"Stack Stop {self.stack_name}"

    @property
    def icon(self):
        """Return the icon of the button."""
        return "mdi:stop-circle"

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.CONFIG

    async def async_press(self):
        """Handle the button press."""
        try:
            _LOGGER.info("🔄 Stopping stack %s", self.stack_name)
            await self.coordinator.api.stacks.stop_stack(self.coordinator.endpoint_id, self.stack_name)
            
            # Trigger a refresh to update the state
            await self.coordinator.async_request_refresh()
            
            # Small delay to allow the state to propagate
            import asyncio
            await asyncio.sleep(2)
            
            _LOGGER.debug("✅ Stack %s stopped successfully", self.stack_name)
            
        except Exception as e:
            _LOGGER.error("❌ Error stopping stack %s: %s", self.stack_name, e)
            raise

class StackStartButton(BaseStackEntity, ButtonEntity):
    """Button for starting a stack."""

    @property
    def entity_type(self) -> str:
        return "stack_start"

    @property
    def name(self) -> str:
        """Return the name of the button."""
        return f"Stack Start {self.stack_name}"

    @property
    def icon(self):
        """Return the icon of the button."""
        return "mdi:play-circle"

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.CONFIG

    async def async_press(self):
        """Handle the button press."""
        try:
            _LOGGER.info("🔄 Starting stack %s", self.stack_name)
            await self.coordinator.api.stacks.start_stack(self.coordinator.endpoint_id, self.stack_name)
            
            # Trigger a refresh to update the state
            await self.coordinator.async_request_refresh()
            
            # Small delay to allow the state to propagate
            import asyncio
            await asyncio.sleep(2)
            
            _LOGGER.debug("✅ Stack %s started successfully", self.stack_name)
            
        except Exception as e:
            _LOGGER.error("❌ Error starting stack %s: %s", self.stack_name, e)
            raise

class StackUpdateButton(BaseStackEntity, ButtonEntity):
    """Button to trigger force update of a Portainer stack (pull + redeploy)."""

    @property
    def entity_type(self) -> str:
        return "stack_update"

    @property
    def name(self) -> str:
        """Return the name of the button."""
        return f"Stack Update {self.stack_name}"

    @property
    def icon(self):
        """Return the icon of the button."""
        return "mdi:update"

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.CONFIG

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            _LOGGER.info("🔄 Force updating stack %s", self.stack_name)
            result = await self.coordinator.api.stacks.update_stack(self.coordinator.endpoint_id, self.stack_name)
            
            # Accept either successful PUT or fallback start, and require readiness wait to pass
            success = (
                result.get("wait_ready", False)
                and (
                    result.get("update_put", {}).get("ok", False)
                    or result.get("started", False)
                )
            )
            
            if success:
                _LOGGER.info("✅ Stack %s updated successfully: %s", self.stack_name, result)
            else:
                _LOGGER.error("❌ Stack %s update failed: %s", self.stack_name, result)
                # Don't throw exception, just log the error and provide user feedback
                _LOGGER.warning("⚠️ Stack update failed but continuing - check logs for details")
            
            # Trigger a refresh to update the state
            await self.coordinator.async_request_refresh()
            
            # Small delay to allow the state to propagate
            import asyncio
            await asyncio.sleep(2)
            
        except Exception as e:
            _LOGGER.error("❌ Error updating stack %s: %s", self.stack_name, e)
            # Don't re-raise the exception, just log it
            _LOGGER.warning("⚠️ Stack update encountered an error but continuing - check logs for details")

class BulkStartAllButton(BaseContainerEntity, ButtonEntity):
    """Button for starting all containers."""

    def __init__(self, coordinator, entry_id):
        """Initialize the bulk start button."""
        super().__init__(coordinator, entry_id, "bulk_start", "Bulk Start All", {})

    @property
    def entity_type(self) -> str:
        return "bulk_start_all"

    @property
    def name(self) -> str:
        """Return the name of the button."""
        return "Start All Containers"

    @property
    def icon(self):
        """Return the icon of the button."""
        return "mdi:play-circle-multiple"

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.CONFIG

    async def async_press(self):
        """Handle the button press."""
        try:
            _LOGGER.info("🔄 Starting all containers")
            
            # Start all containers
            for container_id in self.coordinator.containers.keys():
                try:
                    await self.coordinator.api.start_container(self.coordinator.endpoint_id, container_id)
                except Exception as e:
                    _LOGGER.warning("⚠️ Failed to start container %s: %s", container_id, e)
            
            # Trigger a refresh to update the state
            await self.coordinator.async_request_refresh()
            
            # Small delay to allow the state to propagate
            import asyncio
            await asyncio.sleep(2)
            
            _LOGGER.debug("✅ All containers started successfully")
            
        except Exception as e:
            _LOGGER.error("❌ Error starting all containers: %s", e)
            raise

class BulkStopAllButton(BaseContainerEntity, ButtonEntity):
    """Button for stopping all containers."""

    def __init__(self, coordinator, entry_id):
        """Initialize the bulk stop button."""
        super().__init__(coordinator, entry_id, "bulk_stop", "Bulk Stop All", {})

    @property
    def entity_type(self) -> str:
        return "bulk_stop_all"

    @property
    def name(self) -> str:
        """Return the name of the button."""
        return "Stop All Containers"

    @property
    def icon(self):
        """Return the icon of the button."""
        return "mdi:stop-circle-multiple"

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.CONFIG

    async def async_press(self):
        """Handle the button press."""
        try:
            _LOGGER.info("🔄 Stopping all containers")
            
            # Stop all containers
            for container_id in self.coordinator.containers.keys():
                try:
                    await self.coordinator.api.stop_container(self.coordinator.endpoint_id, container_id)
                except Exception as e:
                    _LOGGER.warning("⚠️ Failed to stop container %s: %s", container_id, e)
            
            # Trigger a refresh to update the state
            await self.coordinator.async_request_refresh()
            
            # Small delay to allow the state to propagate
            import asyncio
            await asyncio.sleep(2)
            
            _LOGGER.debug("✅ All containers stopped successfully")
            
        except Exception as e:
            _LOGGER.error("❌ Error stopping all containers: %s", e)
            raise
