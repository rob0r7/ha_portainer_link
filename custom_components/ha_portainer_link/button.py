import logging
import asyncio
from datetime import timedelta
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN
from .entity import BaseContainerEntity, BaseStackEntity
from .coordinator import PortainerDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
_LOGGER.info("Loaded Portainer button integration.")

async def async_setup_entry(hass, entry, async_add_entities):
    config = entry.data
    endpoint_id = config["endpoint_id"]
    entry_id = entry.entry_id

    _LOGGER.info("🚀 Setting up HA Portainer Link buttons for entry %s (endpoint %s)", entry_id, endpoint_id)
    
    # Get coordinator
    coordinator = hass.data[DOMAIN][f"{entry_id}_coordinator"]
    
    # Wait for initial data
    await coordinator.async_config_entry_first_refresh()

    buttons = []
    added_stacks = set()  # To prevent duplicate stack buttons
    
    # Create individual container buttons for all containers
    for container_id, container_data in coordinator.containers.items():
        container_name = container_data.get("Names", ["unknown"])[0].strip("/")
        
        # Get stack information
        stack_info = coordinator.get_container_stack_info(container_data)
        
        _LOGGER.debug("🔍 Processing container: %s (ID: %s)", container_name, container_id)
        
        # Create individual container buttons for all containers
        buttons.append(RestartContainerButton(coordinator, entry_id, container_id, container_name, stack_info))
        buttons.append(PullUpdateButton(coordinator, entry_id, container_id, container_name, stack_info))
        
        # Add stack-level buttons only once per stack
        if stack_info.get("is_stack_container"):
            stack_name = stack_info.get("stack_name")
            if stack_name and stack_name not in added_stacks:
                buttons.append(StackStopButton(coordinator, entry_id, stack_name))
                buttons.append(StackStartButton(coordinator, entry_id, stack_name))
                buttons.append(StackUpdateButton(coordinator, entry_id, stack_name))
                added_stacks.add(stack_name)

    _LOGGER.info("✅ Created %d button entities", len(buttons))
    async_add_entities(buttons, update_before_add=True)

class RestartContainerButton(BaseContainerEntity, ButtonEntity):
    """Button to restart a Docker container."""

    @property
    def entity_type(self) -> str:
        return "restart"

    @property
    def name(self) -> str:
        """Return the name of the button."""
        display_name = self._get_container_name_display()
        return f"Restart {display_name}"

    @property
    def icon(self) -> str:
        return "mdi:restart"

    @property
    def available(self) -> bool:
        """Return True if the button should be available."""
        return True

    async def async_press(self) -> None:
        """Restart the Docker container."""
        await self.coordinator.api.restart_container(self.coordinator.endpoint_id, self.container_id)

    async def async_update(self):
        """Update the button status."""
        # Restart button is always available for running containers
        pass

class PullUpdateButton(BaseContainerEntity, ButtonEntity):
    """Button to pull the latest image update for a Docker container."""

    def __init__(self, coordinator, entry_id, container_id, container_name, stack_info):
        """Initialize the pull update button."""
        super().__init__(coordinator, entry_id, container_id, container_name, stack_info)
        self._attr_available = True
        self._has_update = False  # Will be updated in async_update

    @property
    def entity_type(self) -> str:
        return "pull_update"

    @property
    def name(self) -> str:
        """Return the name of the button."""
        display_name = self._get_container_name_display()
        return f"Update {display_name}"

    @property
    def icon(self) -> str:
        return "mdi:download"

    @property
    def available(self) -> bool:
        """Return True if the button should be available."""
        # Temporarily disabled - always return False
        return False

    async def async_update(self):
        """Update the button availability based on update status."""
        # Temporarily disabled
        pass

    async def async_press(self) -> None:
        """Pull the latest image update for the Docker container."""
        try:
            _LOGGER.info("🚀 Starting pull update process for %s", self.container_name)
            
            # Get container status for debugging
            container_info = await self.coordinator.api.inspect_container(self.coordinator.endpoint_id, self.container_id)
            container_status = container_info.get("State", {}).get("Status", "unknown") if container_info else "unknown"
            _LOGGER.info("📊 Container %s status: %s", self.container_name, container_status)
            
            # Always proceed with pull attempt (user wants to force update)
            _LOGGER.info("🔍 Proceeding with pull operation for %s...", self.container_name)
            self._attr_available = False
            
            success = await self.coordinator.api.pull_image_update(self.coordinator.endpoint_id, self.container_id)
            if success:
                _LOGGER.info("✅ SUCCESS: Successfully pulled image update for %s", self.container_name)
                
                # Recreate the container to use the new image
                # Note: This will stop, remove, and recreate the container, which may cause downtime
                _LOGGER.info("🔄 Recreating container to use new image...")
                recreate_success = await self.coordinator.api.recreate_container_with_new_image(self.coordinator.endpoint_id, self.container_id)
                if recreate_success:
                    _LOGGER.info("✅ Container recreated successfully to use new image")
                    await self._send_notification("✅ Update Complete", f"Successfully updated and recreated {self.container_name}")
                    
                    # Wait longer for the container to fully start and Docker to update image info
                    _LOGGER.info("⏳ Waiting for container to fully start and image info to update...")
                    await asyncio.sleep(10)
                    
                    # First refresh attempt
                    _LOGGER.info("🔄 First sensor refresh attempt...")
                    await self._refresh_all_sensors()
                    
                    # Wait a bit more and refresh again to ensure we get the latest data
                    _LOGGER.info("⏳ Waiting additional time for Docker to update container info...")
                    await asyncio.sleep(5)
                    
                    # Second refresh attempt
                    _LOGGER.info("🔄 Second sensor refresh attempt...")
                    await self._refresh_all_sensors()
                    
                    _LOGGER.info("✅ All sensor refresh attempts completed for %s", self.container_name)
                else:
                    _LOGGER.warning("⚠️ Image pulled but container recreation failed")
                    await self._send_notification("⚠️ Update Partial", f"Image pulled for {self.container_name} but recreation failed")
                
                # Update the status after successful pull
                self._has_update = False
                self.async_write_ha_state()
            else:
                _LOGGER.error("❌ FAILED: Failed to pull image update for %s", self.container_name)
                # Send a notification for failure
                await self._send_notification("❌ Update Failed", f"Failed to pull update for {self.container_name}")
        except Exception as e:
            _LOGGER.exception("❌ ERROR: Error pulling image update for %s: %s", self.container_name, e)
        finally:
            self._attr_available = True

    async def _refresh_all_sensors(self):
        """Refresh all sensors for this container."""
        try:
            # List of all sensor entities for this container
            sensor_entities = [
                f"binary_sensor.entry_{self.entry_id}_endpoint_{self.coordinator.endpoint_id}_{self.container_id}_update_available",
                f"sensor.entry_{self.entry_id}_endpoint_{self.coordinator.endpoint_id}_{self.container_id}_current_version",
                f"sensor.entry_{self.entry_id}_endpoint_{self.coordinator.endpoint_id}_{self.container_id}_available_version",
                f"sensor.entry_{self.entry_id}_endpoint_{self.coordinator.endpoint_id}_{self.container_id}_status",
                f"sensor.entry_{self.entry_id}_endpoint_{self.coordinator.endpoint_id}_{self.container_id}_cpu_usage",
                f"sensor.entry_{self.entry_id}_endpoint_{self.coordinator.endpoint_id}_{self.container_id}_memory_usage",
                f"sensor.entry_{self.entry_id}_endpoint_{self.coordinator.endpoint_id}_{self.container_id}_uptime",
                f"sensor.entry_{self.entry_id}_endpoint_{self.coordinator.endpoint_id}_{self.container_id}_image"
            ]
            
            _LOGGER.info("🔄 Refreshing all sensors for %s", self.container_name)
            
            # Refresh each sensor with better error handling
            refreshed_count = 0
            for entity_id in sensor_entities:
                try:
                    await self.hass.services.async_call(
                        "homeassistant",
                        "update_entity",
                        {"entity_id": entity_id},
                        blocking=True  # Make it blocking to ensure it completes
                    )
                    refreshed_count += 1
                    _LOGGER.debug("✅ Refreshed sensor: %s", entity_id)
                except Exception as e:
                    _LOGGER.warning("⚠️ Could not refresh sensor %s: %s", entity_id, e)
            
            _LOGGER.info("✅ Successfully refreshed %d/%d sensors for %s", 
                        refreshed_count, len(sensor_entities), self.container_name)
            
            # Also refresh the binary sensor specifically
            await self._refresh_binary_sensor()
            
            # Force refresh version sensors specifically
            await self._refresh_version_sensors()
            
        except Exception as e:
            _LOGGER.error("❌ Could not refresh sensors: %s", e)

    async def _refresh_version_sensors(self):
        """Force refresh version-related sensors specifically."""
        try:
            version_sensors = [
                f"sensor.entry_{self.entry_id}_endpoint_{self.coordinator.endpoint_id}_{self.container_id}_current_version",
                f"sensor.entry_{self.entry_id}_endpoint_{self.coordinator.endpoint_id}_{self.container_id}_available_version",
                f"binary_sensor.entry_{self.entry_id}_endpoint_{self.coordinator.endpoint_id}_{self.container_id}_update_available"
            ]
            
            _LOGGER.info("🔄 Force refreshing version sensors for %s", self.container_name)
            
            for entity_id in version_sensors:
                try:
                    # Call the service multiple times to ensure it updates
                    for attempt in range(3):
                        await self.hass.services.async_call(
                            "homeassistant",
                            "update_entity",
                            {"entity_id": entity_id},
                            blocking=True
                        )
                        await asyncio.sleep(1)  # Small delay between attempts
                    
                    _LOGGER.debug("✅ Force refreshed version sensor: %s", entity_id)
                except Exception as e:
                    _LOGGER.warning("⚠️ Could not force refresh version sensor %s: %s", entity_id, e)
            
            _LOGGER.info("✅ Version sensors force refresh completed for %s", self.container_name)
        except Exception as e:
            _LOGGER.error("❌ Could not force refresh version sensors: %s", e)

    async def _refresh_binary_sensor(self):
        """Refresh the update available binary sensor."""
        try:
            # Find the binary sensor entity for this container using the same container_id
            binary_sensor_entity_id = f"binary_sensor.entry_{self.entry_id}_endpoint_{self.coordinator.endpoint_id}_{self.container_id}_update_available"
            
            _LOGGER.info("Refreshing binary sensor: %s", binary_sensor_entity_id)
            
            # Trigger a refresh of the binary sensor
            await self.hass.services.async_call(
                "homeassistant",
                "update_entity",
                {"entity_id": binary_sensor_entity_id},
                blocking=False
            )
            _LOGGER.info("✅ Binary sensor refresh triggered successfully for %s", binary_sensor_entity_id)
        except Exception as e:
            _LOGGER.error("❌ Could not refresh binary sensor: %s", e)

    async def _send_notification(self, title, message):
        """Send a notification to the user."""
        try:
            # Try to send to mobile app first
            await self.hass.services.async_call(
                "notify",
                "mobile_app",
                {
                    "title": title,
                    "message": message
                },
                blocking=False
            )
            _LOGGER.info("Notification sent: %s - %s", title, message)
        except Exception as e:
            # If mobile app fails, try persistent notification
            try:
                await self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": title,
                        "message": message
                    },
                    blocking=False
                )
                _LOGGER.info("Persistent notification sent: %s - %s", title, message)
            except Exception as e2:
                _LOGGER.debug("Could not send notification: %s, %s", e, e2)

class StackStopButton(BaseStackEntity, ButtonEntity):
    """Button to stop all containers in a Docker stack."""

    @property
    def entity_type(self) -> str:
        return "stop"

    @property
    def name(self) -> str:
        """Return the name of the button."""
        return f"Stop {self.stack_name}"

    @property
    def icon(self) -> str:
        return "mdi:stop-circle"

    @property
    def available(self) -> bool:
        """Return True if the button should be available."""
        return True

    async def async_update(self):
        """Update the button availability."""
        pass

    async def async_press(self) -> None:
        """Stop all containers in the Docker stack."""
        try:
            _LOGGER.info("🛑 Starting stack stop process for %s", self.stack_name)
            
            success = await self.coordinator.api.stop_stack(self.coordinator.endpoint_id, self.stack_name)
            if success:
                _LOGGER.info("✅ SUCCESS: Successfully stopped stack %s", self.stack_name)
                await self._send_notification("✅ Stack Stopped", f"Successfully stopped stack {self.stack_name}")
            else:
                _LOGGER.error("❌ FAILED: Failed to stop stack %s", self.stack_name)
                await self._send_notification("❌ Stack Stop Failed", f"Failed to stop stack {self.stack_name}")
        except Exception as e:
            _LOGGER.exception("❌ ERROR: Error stopping stack %s: %s", self.stack_name, e)
            await self._send_notification("❌ Stack Stop Error", f"Error stopping stack {self.stack_name}: {str(e)}")

    async def _send_notification(self, title, message):
        """Send a notification to the user."""
        try:
            # Try to send to mobile app first
            await self.hass.services.async_call(
                "notify",
                "mobile_app",
                {
                    "title": title,
                    "message": message
                },
                blocking=False
            )
            _LOGGER.info("Notification sent: %s - %s", title, message)
        except Exception as e:
            # If mobile app fails, try persistent notification
            try:
                await self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": title,
                        "message": message
                    },
                    blocking=False
                )
                _LOGGER.info("Persistent notification sent: %s - %s", title, message)
            except Exception as e2:
                _LOGGER.debug("Could not send notification: %s, %s", e, e2)

class StackStartButton(BaseStackEntity, ButtonEntity):
    """Button to start all containers in a Docker stack."""

    @property
    def entity_type(self) -> str:
        return "start"

    @property
    def name(self) -> str:
        """Return the name of the button."""
        return f"Start {self.stack_name}"

    @property
    def icon(self) -> str:
        return "mdi:play-circle"

    @property
    def available(self) -> bool:
        """Return True if the button should be available."""
        return True

    async def async_update(self):
        """Update the button availability."""
        pass

    async def async_press(self) -> None:
        """Start all containers in the Docker stack."""
        try:
            _LOGGER.info("▶️ Starting stack start process for %s", self.stack_name)
            
            success = await self.coordinator.api.start_stack(self.coordinator.endpoint_id, self.stack_name)
            if success:
                _LOGGER.info("✅ SUCCESS: Successfully started stack %s", self.stack_name)
                await self._send_notification("✅ Stack Started", f"Successfully started stack {self.stack_name}")
            else:
                _LOGGER.error("❌ FAILED: Failed to start stack %s", self.stack_name)
                await self._send_notification("❌ Stack Start Failed", f"Failed to start stack {self.stack_name}")
        except Exception as e:
            _LOGGER.exception("❌ ERROR: Error starting stack %s: %s", self.stack_name, e)
            await self._send_notification("❌ Stack Start Error", f"Error starting stack {self.stack_name}: {str(e)}")

    async def _send_notification(self, title, message):
        """Send a notification to the user."""
        try:
            # Try to send to mobile app first
            await self.hass.services.async_call(
                "notify",
                "mobile_app",
                {
                    "title": title,
                    "message": message
                },
                blocking=False
            )
            _LOGGER.info("Notification sent: %s - %s", title, message)
        except Exception as e:
            # If mobile app fails, try persistent notification
            try:
                await self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": title,
                        "message": message
                    },
                    blocking=False
                )
                _LOGGER.info("Persistent notification sent: %s - %s", title, message)
            except Exception as e2:
                _LOGGER.debug("Could not send notification: %s, %s", e, e2)

class StackUpdateButton(BaseStackEntity, ButtonEntity):
    """Button to force update entire stack with image pulling and redeployment."""

    @property
    def entity_type(self) -> str:
        return "update"

    @property
    def name(self) -> str:
        """Return the name of the button."""
        return f"Force Update {self.stack_name}"

    @property
    def icon(self) -> str:
        return "mdi:update"

    @property
    def available(self) -> bool:
        """Return True if the button should be available."""
        # Temporarily disabled - always return False
        return False

    async def async_update(self):
        """Update the button availability."""
        # Temporarily disabled
        pass

    async def async_press(self) -> None:
        """Force update entire stack with image pulling and redeployment."""
        try:
            _LOGGER.info("🔄 Starting stack force update process for %s", self.stack_name)
            _LOGGER.info("🔍 Stack details: name=%s, endpoint_id=%s", self.stack_name, self.coordinator.endpoint_id)
            
            success = await self.coordinator.api.update_stack(self.coordinator.endpoint_id, self.stack_name)
            if success:
                _LOGGER.info("✅ SUCCESS: Successfully force updated stack %s", self.stack_name)
                await self._send_notification("✅ Stack Force Updated", f"Successfully force updated stack {self.stack_name} with image pulling and redeployment")
            else:
                _LOGGER.error("❌ FAILED: Failed to force update stack %s", self.stack_name)
                await self._send_notification("❌ Stack Force Update Failed", f"Failed to force update stack {self.stack_name}. Check Home Assistant logs for details.")
        except Exception as e:
            _LOGGER.exception("❌ ERROR: Error force updating stack %s: %s", self.stack_name, e)
            await self._send_notification("❌ Stack Force Update Error", f"Error force updating stack {self.stack_name}: {str(e)}")

    async def _send_notification(self, title, message):
        """Send a notification to the user."""
        try:
            # Try to send to mobile app first
            await self.hass.services.async_call(
                "notify",
                "mobile_app",
                {
                    "title": title,
                    "message": message
                },
                blocking=False
            )
            _LOGGER.info("Notification sent: %s - %s", title, message)
        except Exception as e:
            # If mobile app fails, try persistent notification
            try:
                await self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": title,
                        "message": message
                    },
                    blocking=False
                )
                _LOGGER.info("Persistent notification sent: %s - %s", title, message)
            except Exception as e2:
                _LOGGER.debug("Could not send notification: %s, %s", e, e2)
