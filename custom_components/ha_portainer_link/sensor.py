import logging
from homeassistant.const import STATE_UNKNOWN
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .entity import BaseContainerEntity, BaseStackEntity
from .coordinator import PortainerDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
_LOGGER.info("Loaded Portainer sensor integration.")

async def async_setup_entry(hass, entry, async_add_entities):
    config = dict(entry.data)  # Create mutable copy
    endpoint_id = config["endpoint_id"]
    entry_id = entry.entry_id

    _LOGGER.info("🚀 Setting up HA Portainer Link sensors for entry %s (endpoint %s)", entry_id, endpoint_id)
    
    # Get coordinator
    coordinator = hass.data[DOMAIN][f"{entry_id}_coordinator"]
    
    # Check if sensors are enabled using coordinator
    resource_sensors_enabled = coordinator.is_resource_sensors_enabled()
    version_sensors_enabled = coordinator.is_version_sensors_enabled()
    
    _LOGGER.info("📊 Sensor configuration: Resource sensors=%s, Version sensors=%s", 
                 resource_sensors_enabled, version_sensors_enabled)
    
    # Always create status sensors (core functionality). If other sensors are disabled, only status sensors will be created.
    any_sensors_enabled = resource_sensors_enabled or version_sensors_enabled or coordinator.is_stack_view_enabled()
    if not any_sensors_enabled:
        _LOGGER.info("ℹ️ Only status sensors will be created (other sensor types disabled)")
    
    # Coordinator data is already loaded in main setup
    entities = []
    
    # Create sensors for all containers
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
        
        # Always create status sensor (core functionality)
        entities.append(ContainerStatusSensor(coordinator, entry_id, container_id, container_name, stack_info))
        
        # Create resource sensors only if enabled
        if resource_sensors_enabled:
            entities.append(ContainerCPUSensor(coordinator, entry_id, container_id, container_name, stack_info))
            entities.append(ContainerMemorySensor(coordinator, entry_id, container_id, container_name, stack_info))
            entities.append(ContainerUptimeSensor(coordinator, entry_id, container_id, container_name, stack_info))
        
        # Create image and version sensors only if enabled
        if version_sensors_enabled:
            entities.append(ContainerImageSensor(coordinator, entry_id, container_id, container_name, stack_info))
            entities.append(ContainerCurrentVersionSensor(coordinator, entry_id, container_id, container_name, stack_info))
            entities.append(ContainerAvailableVersionSensor(coordinator, entry_id, container_id, container_name, stack_info))
            entities.append(ContainerCurrentDigestSensor(coordinator, entry_id, container_id, container_name, stack_info))
            entities.append(ContainerAvailableDigestSensor(coordinator, entry_id, container_id, container_name, stack_info))

    # Create stack-level sensors if stack view is enabled
    if coordinator.is_stack_view_enabled():
        for stack_name, stack_data in coordinator.stacks.items():
            _LOGGER.debug("🔍 Creating stack sensors for: %s", stack_name)
            
            # Create stack status sensor
            entities.append(StackStatusSensor(coordinator, entry_id, stack_name))
            
            # Create stack container count sensor
            entities.append(StackContainerCountSensor(coordinator, entry_id, stack_name))
    
    _LOGGER.info("✅ Created %d sensor entities", len(entities))
    async_add_entities(entities, update_before_add=True)

class ContainerStatusSensor(BaseContainerEntity, SensorEntity):
    """Sensor for container status."""

    @property
    def entity_type(self) -> str:
        return "status"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        display_name = self._get_container_name_display()
        if self.stack_info.get("is_stack_container"):
            return f"Container Status {display_name}"
        else:
            return f"Status {display_name}"

    @property
    def state(self):
        """Return a normalized container state string."""
        container_data = self._get_container_data()
        if not container_data:
            return STATE_UNKNOWN
        raw_state = container_data.get("State")
        if isinstance(raw_state, dict):
            # Prefer explicit Running flag, then textual Status
            if raw_state.get("Running") is True:
                return "running"
            status_text = raw_state.get("Status") or raw_state.get("State")
            if isinstance(status_text, str) and status_text:
                return status_text
            return "exited"
        if isinstance(raw_state, str):
            return raw_state
        return STATE_UNKNOWN

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return {
            "running": "mdi:docker",
            "exited": "mdi:close-circle",
            "paused": "mdi:pause-circle",
        }.get(self.state, "mdi:help-circle")

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.DIAGNOSTIC

class ContainerCPUSensor(BaseContainerEntity, SensorEntity):
    """Sensor for container CPU usage."""

    @property
    def entity_type(self) -> str:
        return "cpu_usage"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        display_name = self._get_container_name_display()
        if self.stack_info.get("is_stack_container"):
            return f"Container CPU {display_name}"
        else:
            return f"CPU {display_name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        # This will be updated by the coordinator
        return getattr(self, '_state', STATE_UNKNOWN)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "%"

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:cpu-64-bit"

    async def async_update(self):
        """Update the sensor."""
        try:
            container_data = self._get_container_data()
            if not container_data:
                self._state = STATE_UNKNOWN
                return

            # Get container stats
            stats = await self.coordinator.api.get_container_stats(
                self.coordinator.endpoint_id, self.container_id
            )
            
            if stats and "cpu_stats" in stats:
                cpu_stats = stats["cpu_stats"]
                precpu_stats = stats.get("precpu_stats", {})
                
                # Calculate CPU usage percentage
                cpu_delta = cpu_stats.get("cpu_usage", {}).get("total", 0) - precpu_stats.get("cpu_usage", {}).get("total", 0)
                system_delta = cpu_stats.get("system_cpu_usage", 0) - precpu_stats.get("system_cpu_usage", 0)
                
                if system_delta > 0:
                    cpu_percent = (cpu_delta / system_delta) * 100
                    self._state = round(cpu_percent, 2)
                else:
                    self._state = 0.0
            else:
                self._state = STATE_UNKNOWN
                
        except Exception as e:
            _LOGGER.error("❌ Error updating CPU sensor for container %s: %s", self.container_id, e)
            self._state = STATE_UNKNOWN

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.DIAGNOSTIC

class ContainerMemorySensor(BaseContainerEntity, SensorEntity):
    """Sensor for container memory usage."""

    @property
    def entity_type(self) -> str:
        return "memory_usage"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        display_name = self._get_container_name_display()
        if self.stack_info.get("is_stack_container"):
            return f"Container Memory {display_name}"
        else:
            return f"Memory {display_name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        # This will be updated by the coordinator
        return getattr(self, '_state', STATE_UNKNOWN)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "MB"

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:memory"

    async def async_update(self):
        """Update the sensor."""
        try:
            container_data = self._get_container_data()
            if not container_data:
                self._state = STATE_UNKNOWN
                return

            # Get container stats
            stats = await self.coordinator.api.get_container_stats(
                self.coordinator.endpoint_id, self.container_id
            )
            
            if stats and "memory_stats" in stats:
                memory_stats = stats["memory_stats"]
                usage = memory_stats.get("usage", 0)
                
                # Convert bytes to MB
                memory_mb = usage / (1024 * 1024)
                self._state = round(memory_mb, 2)
            else:
                self._state = STATE_UNKNOWN
                
        except Exception as e:
            _LOGGER.error("❌ Error updating memory sensor for container %s: %s", self.container_id, e)
            self._state = STATE_UNKNOWN

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.DIAGNOSTIC

class ContainerUptimeSensor(BaseContainerEntity, SensorEntity):
    """Sensor for container uptime."""

    @property
    def entity_type(self) -> str:
        return "uptime"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        display_name = self._get_container_name_display()
        if self.stack_info.get("is_stack_container"):
            return f"Container Uptime {display_name}"
        else:
            return f"Uptime {display_name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        # This will be updated by the coordinator
        return getattr(self, '_state', STATE_UNKNOWN)

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:clock-outline"

    async def async_update(self):
        """Update the sensor."""
        try:
            container_data = self._get_container_data()
            if not container_data:
                self._state = STATE_UNKNOWN
                return

            # Get container inspection data to get the actual start time
            container_info = await self.coordinator.api.inspect_container(
                self.coordinator.endpoint_id, self.container_id
            )
            
            if container_info and "State" in container_info:
                # Get the container start time
                started_at = container_info["State"].get("StartedAt")
                if started_at:
                    # Parse the Docker timestamp format
                    import datetime
                    try:
                        # Docker timestamps are in ISO format with 'Z' suffix
                        start_time = datetime.datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                        current_time = datetime.datetime.now(datetime.timezone.utc)
                        
                        # Calculate uptime
                        uptime_delta = current_time - start_time
                        uptime_seconds = uptime_delta.total_seconds()
                        
                        # Convert to human readable format
                        if uptime_seconds < 60:
                            self._state = f"{int(uptime_seconds)}s"
                        elif uptime_seconds < 3600:
                            minutes = int(uptime_seconds / 60)
                            self._state = f"{minutes}m"
                        elif uptime_seconds < 86400:
                            hours = int(uptime_seconds / 3600)
                            self._state = f"{hours}h"
                        else:
                            days = int(uptime_seconds / 86400)
                            self._state = f"{days}d"
                    except Exception as e:
                        _LOGGER.error("❌ Error parsing container start time for %s: %s", self.container_id, e)
                        self._state = STATE_UNKNOWN
                else:
                    # Container not started or no start time available
                    self._state = "0s"
            else:
                self._state = STATE_UNKNOWN
                
        except Exception as e:
            _LOGGER.error("❌ Error updating uptime sensor for container %s: %s", self.container_id, e)
            self._state = STATE_UNKNOWN

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.DIAGNOSTIC

class ContainerImageSensor(BaseContainerEntity, SensorEntity):
    """Sensor for container image information."""

    @property
    def entity_type(self) -> str:
        return "image"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        display_name = self._get_container_name_display()
        return f"Image {display_name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        # This will be updated by the coordinator
        return getattr(self, '_state', STATE_UNKNOWN)

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:docker"

    async def async_update(self):
        """Update the sensor."""
        try:
            container_data = self._get_container_data()
            if not container_data:
                self._state = STATE_UNKNOWN
                return

            # Get container inspection data
            container_info = await self.coordinator.api.inspect_container(
                self.coordinator.endpoint_id, self.container_id
            )
            
            if container_info and "Config" in container_info:
                image_name = container_info["Config"].get("Image", "")
                if image_name:
                    self._state = image_name
                else:
                    self._state = STATE_UNKNOWN
            else:
                self._state = STATE_UNKNOWN
                
        except Exception as e:
            _LOGGER.error("❌ Error updating image sensor for container %s: %s", self.container_id, e)
            self._state = STATE_UNKNOWN

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.DIAGNOSTIC

class ContainerCurrentVersionSensor(BaseContainerEntity, SensorEntity):
    """Sensor for container current version."""

    @property
    def entity_type(self) -> str:
        return "current_version"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        display_name = self._get_container_name_display()
        return f"Current Version {display_name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        # This will be updated by the coordinator
        return getattr(self, '_state', STATE_UNKNOWN)

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:tag"

    async def async_update(self):
        """Update the sensor."""
        try:
            container_data = self._get_container_data()
            if not container_data:
                self._state = STATE_UNKNOWN
                return

            # Get container inspection data
            container_info = await self.coordinator.api.inspect_container(
                self.coordinator.endpoint_id, self.container_id
            )
            
            if container_info and "Image" in container_info:
                image_id = container_info["Image"]
                if image_id:
                    # Get image info to extract version
                    image_info = await self.coordinator.api.get_image_info(
                        self.coordinator.endpoint_id, image_id
                    )
                    if image_info:
                        version = self.coordinator.api.extract_version_from_image(image_info)
                        self._state = version
                    else:
                        self._state = STATE_UNKNOWN
                else:
                    self._state = STATE_UNKNOWN
            else:
                self._state = STATE_UNKNOWN
                
        except Exception as e:
            _LOGGER.error("❌ Error updating current version sensor for container %s: %s", self.container_id, e)
            self._state = STATE_UNKNOWN

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.DIAGNOSTIC

class ContainerAvailableVersionSensor(BaseContainerEntity, SensorEntity):
    """Sensor for container available version."""

    @property
    def entity_type(self) -> str:
        return "available_version"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        display_name = self._get_container_name_display()
        if self.stack_info.get("is_stack_container"):
            return f"Container Available Version {display_name}"
        else:
            return f"Available Version {display_name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        # This will be updated by the coordinator
        return getattr(self, '_state', STATE_UNKNOWN)

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:tag-outline"

    async def async_update(self):
        """Update the sensor."""
        try:
            container_data = self._get_container_data()
            if not container_data:
                self._state = STATE_UNKNOWN
                return

            # Check if update sensors are enabled
            if not self.coordinator.is_update_sensors_enabled():
                self._state = STATE_UNKNOWN
                return

            # Get available version via image API helper
            image_name = None
            container_info = await self.coordinator.api.inspect_container(
                self.coordinator.endpoint_id, self.container_id
            )
            if container_info and "Config" in container_info:
                image_name = container_info["Config"].get("Image")
            if image_name:
                version = await self.coordinator.api.get_available_version(
                    self.coordinator.endpoint_id, image_name
                )
                self._state = version if version else STATE_UNKNOWN
            else:
                self._state = STATE_UNKNOWN
                
        except Exception as e:
            _LOGGER.error("❌ Error updating available version sensor for container %s: %s", self.container_id, e)
            self._state = STATE_UNKNOWN

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.DIAGNOSTIC


class ContainerCurrentDigestSensor(BaseContainerEntity, SensorEntity):
    """Sensor for container current image digest."""

    @property
    def entity_type(self) -> str:
        return "current_digest"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        display_name = self._get_container_name_display()
        if self.stack_info.get("is_stack_container"):
            return f"Container Current Digest {display_name}"
        else:
            return f"Current Digest {display_name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        # This will be updated by the coordinator
        return getattr(self, '_state', STATE_UNKNOWN)

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:fingerprint"

    async def async_update(self):
        """Update the sensor."""
        try:
            container_data = self._get_container_data()
            if not container_data:
                self._state = STATE_UNKNOWN
                return

            # Check if version sensors are enabled
            if not self.coordinator.is_version_sensors_enabled():
                self._state = STATE_UNKNOWN
                return

            # Get current digest from image API
            current_digest = await self.coordinator.api.get_current_digest(
                self.coordinator.endpoint_id, self.container_id
            )
            
            if current_digest and current_digest != "unknown":
                self._state = current_digest
            else:
                self._state = STATE_UNKNOWN
                
        except Exception as e:
            _LOGGER.error("❌ Error updating current digest sensor for container %s: %s", self.container_id, e)
            self._state = STATE_UNKNOWN

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.DIAGNOSTIC


class ContainerAvailableDigestSensor(BaseContainerEntity, SensorEntity):
    """Sensor for container available image digest from registry."""

    @property
    def entity_type(self) -> str:
        return "available_digest"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        display_name = self._get_container_name_display()
        if self.stack_info.get("is_stack_container"):
            return f"Container Available Digest {display_name}"
        else:
            return f"Available Digest {display_name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        # This will be updated by the coordinator
        return getattr(self, '_state', STATE_UNKNOWN)

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:fingerprint-outline"

    async def async_update(self):
        """Update the sensor."""
        try:
            container_data = self._get_container_data()
            if not container_data:
                self._state = STATE_UNKNOWN
                return

            # Check if version sensors are enabled
            if not self.coordinator.is_version_sensors_enabled():
                self._state = STATE_UNKNOWN
                return

            # Get available digest from image API
            available_digest = await self.coordinator.api.get_available_digest(
                self.coordinator.endpoint_id, self.container_id
            )
            
            if available_digest and available_digest != "unknown":
                self._state = available_digest
            else:
                self._state = STATE_UNKNOWN
                
        except Exception as e:
            _LOGGER.error("❌ Error updating available digest sensor for container %s: %s", self.container_id, e)
            self._state = STATE_UNKNOWN

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.DIAGNOSTIC


class StackStatusSensor(BaseStackEntity, SensorEntity):
    """Sensor for stack status."""

    @property
    def entity_type(self) -> str:
        return "stack_status"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"Stack Status {self.stack_name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        stack_data = self._get_stack_data()
        if stack_data:
            return stack_data.get("Status", STATE_UNKNOWN)
        return STATE_UNKNOWN

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return {
            "active": "mdi:check-circle",
            "inactive": "mdi:close-circle",
            "pending": "mdi:clock",
        }.get(self.state, "mdi:help-circle")

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.DIAGNOSTIC


class StackContainerCountSensor(BaseStackEntity, SensorEntity):
    """Sensor for stack container count."""

    @property
    def entity_type(self) -> str:
        return "stack_container_count"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"Stack Container Count {self.stack_name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        containers = self._get_stack_containers()
        return len(containers) if containers else 0

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:docker"

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.DIAGNOSTIC