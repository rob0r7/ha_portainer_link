import logging
import asyncio
from datetime import timedelta
from homeassistant.components.button import ButtonEntity
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval
from .const import DOMAIN
from .portainer_api import PortainerAPI

_LOGGER = logging.getLogger(__name__)
_LOGGER.info("Loaded Portainer button integration.")

async def async_setup_entry(hass, entry, async_add_entities):
    conf = entry.data
    host = conf["host"]
    username = conf.get("username")
    password = conf.get("password")
    api_key = conf.get("api_key")
    endpoint_id = conf["endpoint_id"]

    api = PortainerAPI(host, username, password, api_key)
    await api.initialize()
    containers = await api.get_containers(endpoint_id)

    buttons = []
    for container in containers:
        name = container.get("Names", ["unknown"])[0].strip("/")
        container_id = container["Id"]
        buttons.append(RestartContainerButton(name, api, endpoint_id, container_id))
        buttons.append(PullUpdateButton(name, api, endpoint_id, container_id))

    async_add_entities(buttons, update_before_add=True)

class RestartContainerButton(ButtonEntity):
    """Button to restart a Docker container."""

    def __init__(self, name, api, endpoint_id, container_id):
        self._attr_name = f"{name} Restart"
        self._container_name = name
        self._api = api
        self._endpoint_id = endpoint_id
        self._container_id = container_id
        self._attr_unique_id = f"{container_id}_restart"
        self._attr_available = True

    @property
    def icon(self):
        return "mdi:restart"

    @property
    def available(self):
        """Return True if the button should be available."""
        return self._attr_available

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._container_id)},
            "name": self._container_name,
            "manufacturer": "Docker via Portainer",
            "model": "Docker Container",
            "configuration_url": f"{self._api.base_url}/#!/containers/{self._container_id}/details",
        }

    async def async_press(self) -> None:
        """Restart the Docker container."""
        await self._api.restart_container(self._endpoint_id, self._container_id)

    async def async_update(self):
        """Update the button status."""
        # Restart button is always available for running containers
        pass


class PullUpdateButton(ButtonEntity):
    """Button to pull the latest image update for a Docker container."""

    def __init__(self, name, api, endpoint_id, container_id):
        self._container_name = name
        self._api = api
        self._endpoint_id = endpoint_id
        self._container_id = container_id
        self._attr_unique_id = f"{container_id}_pull_update"
        self._attr_available = True
        self._has_update = False  # Will be updated in async_update

    @property
    def name(self):
        """Return the name of the button."""
        return f"{self._container_name} Pull Update"

    @property
    def icon(self):
        return "mdi:download"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._container_id)},
            "name": self._container_name,
            "manufacturer": "Docker via Portainer",
            "model": "Docker Container",
            "configuration_url": f"{self._api.base_url}/#!/containers/{self._container_id}/details",
        }

    @property
    def available(self):
        """Return True if the button should be available."""
        return self._attr_available

    async def async_update(self):
        """Update the button availability based on update status."""
        # This method is called by Home Assistant periodically
        pass

    async def async_press(self) -> None:
        """Pull the latest image update for the Docker container."""
        try:
            _LOGGER.info("🚀 Starting pull update process for %s", self._container_name)
            
            # Get container status for debugging
            container_info = await self._api.inspect_container(self._endpoint_id, self._container_id)
            container_status = container_info.get("State", {}).get("Status", "unknown") if container_info else "unknown"
            _LOGGER.info("📊 Container %s status: %s", self._container_name, container_status)
            
            # Always check for updates first
            _LOGGER.info("🔍 Checking for updates for %s...", self._container_name)
            self._has_update = await self._api.check_image_updates(self._endpoint_id, self._container_id)
            _LOGGER.info("📋 Update check result for %s: %s", self._container_name, self._has_update)
            
            if not self._has_update:
                _LOGGER.info("❌ No updates available for %s - pull operation cancelled", self._container_name)
                await self._send_notification("ℹ️ No Updates", f"No updates available for {self._container_name}")
                return
            
            _LOGGER.info("✅ Updates detected for %s - starting pull operation", self._container_name)
            self._attr_available = False
            
            success = await self._api.pull_image_update(self._endpoint_id, self._container_id)
            if success:
                _LOGGER.info("✅ SUCCESS: Successfully pulled image update for %s", self._container_name)
                
                # Recreate the container to use the new image
                # Note: This will stop, remove, and recreate the container, which may cause downtime
                _LOGGER.info("🔄 Recreating container to use new image...")
                recreate_success = await self._api.recreate_container_with_new_image(self._endpoint_id, self._container_id)
                if recreate_success:
                    _LOGGER.info("✅ Container recreated successfully to use new image")
                    await self._send_notification("✅ Update Complete", f"Successfully updated and recreated {self._container_name}")
                    
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
                    
                    _LOGGER.info("✅ All sensor refresh attempts completed for %s", self._container_name)
                else:
                    _LOGGER.warning("⚠️ Image pulled but container recreation failed")
                    await self._send_notification("⚠️ Update Partial", f"Image pulled for {self._container_name} but recreation failed")
                
                # Update the status after successful pull
                self._has_update = False
                self.async_write_ha_state()
            else:
                _LOGGER.error("❌ FAILED: Failed to pull image update for %s", self._container_name)
                # Send a notification for failure
                await self._send_notification("❌ Update Failed", f"Failed to pull update for {self._container_name}")
        except Exception as e:
            _LOGGER.exception("❌ ERROR: Error pulling image update for %s: %s", self._container_name, e)
        finally:
            self._attr_available = True

    async def _refresh_all_sensors(self):
        """Refresh all sensors for this container."""
        try:
            # List of all sensor entities for this container
            sensor_entities = [
                f"binary_sensor.{self._container_id}_update_available",
                f"sensor.{self._container_id}_current_version",
                f"sensor.{self._container_id}_available_version",
                f"sensor.{self._container_id}_status",
                f"sensor.{self._container_id}_cpu_usage",
                f"sensor.{self._container_id}_memory_usage",
                f"sensor.{self._container_id}_uptime",
                f"sensor.{self._container_id}_image"
            ]
            
            _LOGGER.info("🔄 Refreshing all sensors for %s", self._container_name)
            
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
                        refreshed_count, len(sensor_entities), self._container_name)
            
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
                f"sensor.{self._container_id}_current_version",
                f"sensor.{self._container_id}_available_version",
                f"binary_sensor.{self._container_id}_update_available"
            ]
            
            _LOGGER.info("🔄 Force refreshing version sensors for %s", self._container_name)
            
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
            
            _LOGGER.info("✅ Version sensors force refresh completed for %s", self._container_name)
        except Exception as e:
            _LOGGER.error("❌ Could not force refresh version sensors: %s", e)

    async def _refresh_binary_sensor(self):
        """Refresh the update available binary sensor."""
        try:
            # Find the binary sensor entity for this container using the same container_id
            binary_sensor_entity_id = f"binary_sensor.{self._container_id}_update_available"
            
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
