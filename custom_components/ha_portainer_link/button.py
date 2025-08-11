import logging
import hashlib
import asyncio
from datetime import timedelta
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers import entity_registry as er
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from .const import DOMAIN
from .portainer_api import PortainerAPI

_LOGGER = logging.getLogger(__name__)
_LOGGER.info("Loaded Portainer button integration.")

def _build_stable_unique_id(entry_id, endpoint_id, container_or_stack_name, stack_info, suffix):
    if stack_info.get("is_stack_container") and suffix in {"restart", "pull_update"}:
        stack_name = stack_info.get("stack_name", "unknown")
        service_name = stack_info.get("service_name", container_or_stack_name)
        base = f"{stack_name}_{service_name}"
    else:
        base = container_or_stack_name
    sanitized = base.replace('-', '_').replace(' ', '_').replace('/', '_')
    return f"entry_{entry_id}_endpoint_{endpoint_id}_{sanitized}_{suffix}"

def _get_host_display_name(base_url):
    """Extract a clean host name from the base URL for display purposes."""
    # Remove protocol and common ports
    host = base_url.replace("https://", "").replace("http://", "")
    # Remove trailing slash if present
    host = host.rstrip("/")
    # Remove common ports
    for port in [":9000", ":9443", ":80", ":443"]:
        if host.endswith(port):
            host = host[:-len(port)]
    
    # If the host is an IP address, keep it as is
    # If it's a domain, try to extract a meaningful name
    if host.replace('.', '').replace('-', '').replace('_', '').isdigit():
        # It's an IP address, keep as is
        return host
    else:
        # It's a domain, extract the main part
        parts = host.split('.')
        if len(parts) >= 2:
            # Use the main domain part (e.g., "portainer" from "portainer.example.com")
            return parts[0]
        else:
            return host

def _get_host_hash(base_url):
    """Generate a short hash of the host URL for unique identification."""
    return hashlib.md5(base_url.encode()).hexdigest()[:8]

async def async_setup_entry(hass, entry, async_add_entities):
    conf = entry.data
    host = conf["host"]
    username = conf.get("username")
    password = conf.get("password")
    api_key = conf.get("api_key")
    endpoint_id = conf["endpoint_id"]
    entry_id = entry.entry_id

    api = PortainerAPI(host, username, password, api_key)
    await api.initialize()
    containers = await api.get_containers(endpoint_id)

    buttons = []
    added_stacks = set() # To prevent duplicate stack buttons
    
    # Migrate existing button entities to stable unique_ids
    try:
        er_registry = er.async_get(hass)
        for container in containers:
            name = container.get("Names", ["unknown"])[0].strip("/")
            container_id = container["Id"]
            container_info = await api.inspect_container(endpoint_id, container_id)
            stack_info = api.get_container_stack_info(container_info) if container_info else {"is_stack_container": False}
            for suffix, domain_name in [("restart", "button"), ("pull_update", "button")]:
                old_uid = f"entry_{entry_id}_endpoint_{endpoint_id}_{container_id}_{suffix}"
                new_uid = _build_stable_unique_id(entry_id, endpoint_id, name, stack_info, suffix)
                if old_uid != new_uid:
                    ent_id = er_registry.async_get_entity_id(domain_name, DOMAIN, old_uid)
                    if ent_id:
                        try:
                            er_registry.async_update_entity(ent_id, new_unique_id=new_uid)
                            _LOGGER.debug("Migrated %s unique_id: %s -> %s", ent_id, old_uid, new_uid)
                        except Exception as e:
                            _LOGGER.debug("Could not migrate %s: %s", ent_id, e)
    except Exception as e:
        _LOGGER.debug("Button registry migration skipped/failed: %s", e)
    
    for container in containers:
        name = container.get("Names", ["unknown"])[0].strip("/")
        container_id = container["Id"]
        
        # Get container inspection data to determine if it's part of a stack
        container_info = await api.inspect_container(endpoint_id, container_id)
        stack_info = api.get_container_stack_info(container_info) if container_info else {"is_stack_container": False}
        
        # Create individual container buttons for all containers - they will all belong to the same stack device if they're in a stack
        buttons.append(RestartContainerButton(name, api, endpoint_id, container_id, stack_info, entry_id))
        buttons.append(PullUpdateButton(name, api, endpoint_id, container_id, stack_info, entry_id))
        
        # Add stack-level buttons only once per stack
        if stack_info.get("is_stack_container"):
            stack_name = stack_info.get("stack_name")
            if stack_name and stack_name not in added_stacks:
                buttons.append(StackStopButton(stack_name, api, endpoint_id, stack_info, entry_id))
                buttons.append(StackStartButton(stack_name, api, endpoint_id, stack_info, entry_id))
                buttons.append(StackUpdateButton(stack_name, api, endpoint_id, stack_info, entry_id))
                added_stacks.add(stack_name)

    async_add_entities(buttons, update_before_add=True)

class RestartContainerButton(ButtonEntity):
    """Button to restart a Docker container."""

    def __init__(self, name, api, endpoint_id, container_id, stack_info, entry_id):
        self._attr_name = f"{name} Restart"
        self._container_name = name
        self._api = api
        self._endpoint_id = endpoint_id
        self._container_id = container_id
        self._stack_info = stack_info
        self._entry_id = entry_id
        self._attr_unique_id = _build_stable_unique_id(entry_id, endpoint_id, name, stack_info, "restart")
        self._attr_available = True

    async def _find_current_container_id(self):
        try:
            containers = await self._api.get_containers(self._endpoint_id)
            if not containers:
                return None
            if self._stack_info.get("is_stack_container"):
                expected_stack = self._stack_info.get("stack_name")
                expected_service = self._stack_info.get("service_name")
                for container in containers:
                    labels = container.get("Labels", {}) or {}
                    if (
                        labels.get("com.docker.compose.project") == expected_stack
                        and labels.get("com.docker.compose.service") == expected_service
                    ):
                        return container.get("Id")
            for container in containers:
                names = container.get("Names", []) or []
                if not names:
                    continue
                name = names[0].strip("/")
                if name == self._container_name:
                    return container.get("Id")
        except Exception:
            return None
        return None

    async def _ensure_container_bound(self) -> None:
        try:
            info = await self._api.get_container_info(self._endpoint_id, self._container_id)
            if not info or not isinstance(info, dict) or not info.get("Id"):
                new_id = await self._find_current_container_id()
                if new_id and new_id != self._container_id:
                    self._container_id = new_id
        except Exception:
            new_id = await self._find_current_container_id()
            if new_id and new_id != self._container_id:
                self._container_id = new_id

    @property
    def icon(self):
        return "mdi:restart"

    @property
    def available(self):
        """Return True if the button should be available."""
        return self._attr_available

    @property
    def device_info(self):
        host_name = _get_host_display_name(self._api.base_url)
        host_hash = _get_host_hash(self._api.base_url)
        
        if self._stack_info.get("is_stack_container"):
            # For stack containers, use the stack as the device
            stack_name = self._stack_info.get("stack_name", "unknown_stack")
            # Use a more robust identifier that includes the entry_id, host hash, and host name to prevent duplicates
            device_id = f"entry_{self._entry_id}_endpoint_{self._endpoint_id}_stack_{stack_name}_{host_hash}_{host_name.replace('.', '_').replace(':', '_')}"
            return {
                "identifiers": {(DOMAIN, device_id)},
                "name": f"Stack: {stack_name} ({host_name})",
                "manufacturer": "Docker via Portainer",
                "model": "Docker Stack",
                "configuration_url": f"{self._api.base_url}/#!/stacks/{stack_name}",
            }
        else:
            # For standalone containers, use the container as the device
            device_id = f"entry_{self._entry_id}_endpoint_{self._endpoint_id}_container_{self._container_id}_{host_hash}_{host_name.replace('.', '_').replace(':', '_')}"
            return {
                "identifiers": {(DOMAIN, device_id)},
                "name": f"{self._container_name} ({host_name})",
                "manufacturer": "Docker via Portainer",
                "model": "Docker Container",
                "configuration_url": f"{self._api.base_url}/#!/containers/{self._container_id}/details",
            }

    async def async_press(self) -> None:
        """Restart the Docker container."""
        await self._ensure_container_bound()
        await self._api.restart_container(self._endpoint_id, self._container_id)

    async def async_update(self):
        """Update the button status."""
        # Restart button is always available for running containers
        pass


class PullUpdateButton(ButtonEntity):
    """Button to pull the latest image update for a Docker container."""

    def __init__(self, name, api, endpoint_id, container_id, stack_info, entry_id):
        self._container_name = name
        self._api = api
        self._endpoint_id = endpoint_id
        self._container_id = container_id
        self._stack_info = stack_info
        self._entry_id = entry_id
        self._attr_unique_id = _build_stable_unique_id(entry_id, endpoint_id, name, stack_info, "pull_update")
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
        host_name = _get_host_display_name(self._api.base_url)
        host_hash = _get_host_hash(self._api.base_url)
        
        if self._stack_info.get("is_stack_container"):
            # For stack containers, use the stack as the device
            stack_name = self._stack_info.get("stack_name", "unknown_stack")
            # Use a more robust identifier that includes the entry_id, host hash, and host name to prevent duplicates
            device_id = f"entry_{self._entry_id}_endpoint_{self._endpoint_id}_stack_{stack_name}_{host_hash}_{host_name.replace('.', '_').replace(':', '_')}"
            return {
                "identifiers": {(DOMAIN, device_id)},
                "name": f"Stack: {stack_name} ({host_name})",
                "manufacturer": "Docker via Portainer",
                "model": "Docker Stack",
                "configuration_url": f"{self._api.base_url}/#!/stacks/{stack_name}",
            }
        else:
            # For standalone containers, use the container as the device
            device_id = f"entry_{self._entry_id}_endpoint_{self._endpoint_id}_container_{self._container_id}_{host_hash}_{host_name.replace('.', '_').replace(':', '_')}"
            return {
                "identifiers": {(DOMAIN, device_id)},
                "name": f"{self._container_name} ({host_name})",
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
            await self._ensure_container_bound()
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
                    
                    # After recreation, rebind to the new ID if it changed
                    await self._ensure_container_bound()
                    
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


class StackStopButton(ButtonEntity):
    """Button to stop all containers in a Docker stack."""

    def __init__(self, stack_name, api, endpoint_id, stack_info, entry_id):
        self._stack_name = stack_name
        self._api = api
        self._endpoint_id = endpoint_id
        self._stack_info = stack_info
        self._entry_id = entry_id
        # Stack buttons already stable by stack name, keep format but consistent
        self._attr_unique_id = _build_stable_unique_id(entry_id, endpoint_id, stack_name, {"is_stack_container": True, "stack_name": stack_name, "service_name": stack_name}, "stop")
        self._attr_available = True

    @property
    def name(self):
        """Return the name of the button."""
        return f"Stack: {self._stack_name} Stop"

    @property
    def icon(self):
        return "mdi:stop-circle"

    @property
    def device_info(self):
        host_name = _get_host_display_name(self._api.base_url)
        host_hash = _get_host_hash(self._api.base_url)
        
        if self._stack_info.get("is_stack_container"):
            # For stack containers, use the stack as the device
            stack_name = self._stack_info.get("stack_name", "unknown_stack")
            # Use a more robust identifier that includes the entry_id, host hash, and host name to prevent duplicates
            device_id = f"entry_{self._entry_id}_endpoint_{self._endpoint_id}_stack_{stack_name}_{host_hash}_{host_name.replace('.', '_').replace(':', '_')}"
            return {
                "identifiers": {(DOMAIN, device_id)},
                "name": f"Stack: {stack_name} ({host_name})",
                "manufacturer": "Docker via Portainer",
                "model": "Docker Stack",
                "configuration_url": f"{self._api.base_url}/#!/stacks/{stack_name}",
            }
        else:
            # For standalone containers, use the container as the device
            device_id = f"entry_{self._entry_id}_endpoint_{self._endpoint_id}_container_{self._stack_name}_{host_hash}_{host_name.replace('.', '_').replace(':', '_')}"
            return {
                "identifiers": {(DOMAIN, device_id)},
                "name": f"{self._stack_name} ({host_name})",
                "manufacturer": "Docker via Portainer",
                "model": "Docker Container",
                "configuration_url": f"{self._api.base_url}/#!/containers/{self._stack_name}/details",
            }

    @property
    def available(self):
        """Return True if the button should be available."""
        return self._attr_available

    async def async_update(self):
        """Update the button availability."""
        pass

    async def async_press(self) -> None:
        """Stop all containers in the Docker stack."""
        try:
            _LOGGER.info("🛑 Starting stack stop process for %s", self._stack_name)
            self._attr_available = False
            
            success = await self._api.stop_stack(self._endpoint_id, self._stack_name)
            if success:
                _LOGGER.info("✅ SUCCESS: Successfully stopped stack %s", self._stack_name)
                await self._send_notification("✅ Stack Stopped", f"Successfully stopped stack {self._stack_name}")
            else:
                _LOGGER.error("❌ FAILED: Failed to stop stack %s", self._stack_name)
                await self._send_notification("❌ Stack Stop Failed", f"Failed to stop stack {self._stack_name}")
        except Exception as e:
            _LOGGER.exception("❌ ERROR: Error stopping stack %s: %s", self._stack_name, e)
            await self._send_notification("❌ Stack Stop Error", f"Error stopping stack {self._stack_name}: {str(e)}")
        finally:
            self._attr_available = True

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


class StackStartButton(ButtonEntity):
    """Button to start all containers in a Docker stack."""

    def __init__(self, stack_name, api, endpoint_id, stack_info, entry_id):
        self._stack_name = stack_name
        self._api = api
        self._endpoint_id = endpoint_id
        self._stack_info = stack_info
        self._entry_id = entry_id
        self._attr_unique_id = _build_stable_unique_id(entry_id, endpoint_id, stack_name, {"is_stack_container": True, "stack_name": stack_name, "service_name": stack_name}, "start")
        self._attr_available = True

    @property
    def name(self):
        """Return the name of the button."""
        return f"Stack: {self._stack_name} Start"

    @property
    def icon(self):
        return "mdi:play-circle"

    @property
    def device_info(self):
        host_name = _get_host_display_name(self._api.base_url)
        host_hash = _get_host_hash(self._api.base_url)
        
        if self._stack_info.get("is_stack_container"):
            # For stack containers, use the stack as the device
            stack_name = self._stack_info.get("stack_name", "unknown_stack")
            # Use a more robust identifier that includes the entry_id, host hash, and host name to prevent duplicates
            device_id = f"entry_{self._entry_id}_endpoint_{self._endpoint_id}_stack_{stack_name}_{host_hash}_{host_name.replace('.', '_').replace(':', '_')}"
            return {
                "identifiers": {(DOMAIN, device_id)},
                "name": f"Stack: {stack_name} ({host_name})",
                "manufacturer": "Docker via Portainer",
                "model": "Docker Stack",
                "configuration_url": f"{self._api.base_url}/#!/stacks/{stack_name}",
            }
        else:
            # For standalone containers, use the container as the device
            device_id = f"entry_{self._entry_id}_endpoint_{self._endpoint_id}_container_{self._stack_name}_{host_hash}_{host_name.replace('.', '_').replace(':', '_')}"
            return {
                "identifiers": {(DOMAIN, device_id)},
                "name": f"{self._stack_name} ({host_name})",
                "manufacturer": "Docker via Portainer",
                "model": "Docker Container",
                "configuration_url": f"{self._api.base_url}/#!/containers/{self._stack_name}/details",
            }

    @property
    def available(self):
        """Return True if the button should be available."""
        return self._attr_available

    async def async_update(self):
        """Update the button availability."""
        pass

    async def async_press(self) -> None:
        """Start all containers in the Docker stack."""
        try:
            _LOGGER.info("▶️ Starting stack start process for %s", self._stack_name)
            self._attr_available = False
            
            success = await self._api.start_stack(self._endpoint_id, self._stack_name)
            if success:
                _LOGGER.info("✅ SUCCESS: Successfully started stack %s", self._stack_name)
                await self._send_notification("✅ Stack Started", f"Successfully started stack {self._stack_name}")
            else:
                _LOGGER.error("❌ FAILED: Failed to start stack %s", self._stack_name)
                await self._send_notification("❌ Stack Start Failed", f"Failed to start stack {self._stack_name}")
        except Exception as e:
            _LOGGER.exception("❌ ERROR: Error starting stack %s: %s", self._stack_name, e)
            await self._send_notification("❌ Stack Start Error", f"Error starting stack {self._stack_name}: {str(e)}")
        finally:
            self._attr_available = True

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


class StackUpdateButton(ButtonEntity):
    """Button to update a Docker stack by pulling latest images and applying the stack config."""

    def __init__(self, stack_name, api, endpoint_id, stack_info, entry_id):
        self._stack_name = stack_name
        self._api = api
        self._endpoint_id = endpoint_id
        self._stack_info = stack_info
        self._entry_id = entry_id
        self._attr_unique_id = _build_stable_unique_id(entry_id, endpoint_id, stack_name, {"is_stack_container": True, "stack_name": stack_name, "service_name": stack_name}, "update")
        self._attr_available = True

    @property
    def name(self):
        return f"Stack: {self._stack_name} Update"

    @property
    def icon(self):
        return "mdi:update"

    @property
    def device_info(self):
        host_name = _get_host_display_name(self._api.base_url)
        host_hash = _get_host_hash(self._api.base_url)
        stack_name = self._stack_info.get("stack_name", self._stack_name)
        device_id = f"entry_{self._entry_id}_endpoint_{self._endpoint_id}_stack_{stack_name}_{host_hash}_{host_name.replace('.', '_').replace(':', '_')}"
        return {
            "identifiers": {(DOMAIN, device_id)},
            "name": f"Stack: {stack_name} ({host_name})",
            "manufacturer": "Docker via Portainer",
            "model": "Docker Stack",
            "configuration_url": f"{self._api.base_url}/#!/stacks/{stack_name}",
        }

    @property
    def available(self):
        return self._attr_available

    async def async_update(self):
        pass

    async def async_press(self) -> None:
        try:
            _LOGGER.info("🔄 Starting stack update for %s", self._stack_name)
            self._attr_available = False
            result = await self._api.update_stack(self._endpoint_id, self._stack_name, pull_image=True, prune=False)
            ok = bool(result) and (result.get("update_put", {}).get("ok") or result.get("started") or result.get("wait_ready"))
            if ok:
                _LOGGER.info("✅ SUCCESS: Stack %s updated: %s", self._stack_name, result)
                await self._send_notification("✅ Stack Updated", f"Successfully updated stack {self._stack_name}")
            else:
                _LOGGER.error("❌ FAILED: Stack %s update failed: %s", self._stack_name, result)
                await self._send_notification("❌ Stack Update Failed", f"Failed to update stack {self._stack_name}")
        except Exception as e:
            _LOGGER.exception("❌ ERROR: Error updating stack %s: %s", self._stack_name, e)
            await self._send_notification("❌ Stack Update Error", f"Error updating stack {self._stack_name}: {str(e)}")
        finally:
            self._attr_available = True

    async def _send_notification(self, title, message):
        try:
            await self.hass.services.async_call(
                "notify",
                "mobile_app",
                {"title": title, "message": message},
                blocking=False,
            )
            _LOGGER.info("Notification sent: %s - %s", title, message)
        except Exception as e:
            try:
                await self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {"title": title, "message": message},
                    blocking=False,
                )
                _LOGGER.info("Persistent notification sent: %s - %s", title, message)
            except Exception as e2:
                _LOGGER.debug("Could not send notification: %s, %s", e, e2)
