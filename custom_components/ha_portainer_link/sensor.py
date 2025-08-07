import logging
from homeassistant.const import STATE_UNKNOWN
from homeassistant.components.sensor import SensorEntity

from .const import DOMAIN
from .entity import BaseContainerEntity
from .coordinator import PortainerDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
_LOGGER.info("Loaded Portainer sensor integration.")

async def async_setup_entry(hass, entry, async_add_entities):
    config = entry.data
    endpoint_id = config["endpoint_id"]
    entry_id = entry.entry_id

    _LOGGER.info("🚀 Setting up HA Portainer Link sensors for entry %s (endpoint %s)", entry_id, endpoint_id)
    
    # Get coordinator
    coordinator = hass.data[DOMAIN][f"{entry_id}_coordinator"]
    
    # Wait for initial data
    await coordinator.async_config_entry_first_refresh()

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
        
        # Create sensors for this container
        entities.append(ContainerStatusSensor(coordinator, entry_id, container_id, container_name, stack_info))
        entities.append(ContainerCPUSensor(coordinator, entry_id, container_id, container_name, stack_info))
        entities.append(ContainerMemorySensor(coordinator, entry_id, container_id, container_name, stack_info))
        entities.append(ContainerUptimeSensor(coordinator, entry_id, container_id, container_name, stack_info))
        entities.append(ContainerImageSensor(coordinator, entry_id, container_id, container_name, stack_info))
        entities.append(ContainerCurrentVersionSensor(coordinator, entry_id, container_id, container_name, stack_info))
        entities.append(ContainerAvailableVersionSensor(coordinator, entry_id, container_id, container_name, stack_info))

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
        return f"Status {display_name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        container_data = self._get_container_data()
        if container_data:
            return container_data.get("State", STATE_UNKNOWN)
        return STATE_UNKNOWN

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return {
            "running": "mdi:docker",
            "exited": "mdi:close-circle",
            "paused": "mdi:pause-circle",
        }.get(self.state, "mdi:help-circle")

class ContainerCPUSensor(BaseContainerEntity, SensorEntity):
    """Sensor for container CPU usage."""

    @property
    def entity_type(self) -> str:
        return "cpu_usage"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        display_name = self._get_container_name_display()
        return f"CPU {display_name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        # This will be updated by the coordinator
        return getattr(self, '_state', STATE_UNKNOWN)

    @property
    def unit_of_measurement(self):
        return "%"

    @property
    def icon(self):
        return "mdi:cpu-64-bit"

    async def async_update(self):
        """Update the sensor state."""
        try:
            stats = await self.coordinator.api.get_container_stats(self.coordinator.endpoint_id, self.container_id)
            if stats:
                cpu_usage = stats["cpu_stats"]["cpu_usage"]["total_usage"]
                precpu_usage = stats["precpu_stats"]["cpu_usage"]["total_usage"]
                system_cpu = stats["cpu_stats"]["system_cpu_usage"]
                pre_system_cpu = stats["precpu_stats"]["system_cpu_usage"]

                cpu_delta = cpu_usage - precpu_usage
                system_delta = system_cpu - pre_system_cpu
                cpu_count = stats.get("cpu_stats", {}).get("online_cpus", 1)

                usage = (cpu_delta / system_delta) * cpu_count * 100.0 if system_delta > 0 else 0
                self._state = round(usage, 2)
            else:
                self._state = STATE_UNKNOWN
        except Exception as e:
            _LOGGER.warning("Failed to parse CPU stats for %s: %s", self.name, e)
            self._state = STATE_UNKNOWN

class ContainerMemorySensor(BaseContainerEntity, SensorEntity):
    """Sensor for container memory usage."""

    @property
    def entity_type(self) -> str:
        return "memory_usage"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        display_name = self._get_container_name_display()
        return f"Memory {display_name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return getattr(self, '_state', STATE_UNKNOWN)

    @property
    def unit_of_measurement(self):
        return "MB"

    @property
    def icon(self):
        return "mdi:memory"

    async def async_update(self):
        """Update the sensor state."""
        try:
            stats = await self.coordinator.api.get_container_stats(self.coordinator.endpoint_id, self.container_id)
            if stats:
                mem_bytes = stats["memory_stats"]["usage"]
                self._state = round(mem_bytes / (1024 * 1024), 2)
            else:
                self._state = STATE_UNKNOWN
        except Exception as e:
            _LOGGER.warning("Failed to parse memory stats for %s: %s", self.name, e)
            self._state = STATE_UNKNOWN

class ContainerUptimeSensor(BaseContainerEntity, SensorEntity):
    """Sensor for container uptime."""

    @property
    def entity_type(self) -> str:
        return "uptime"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        display_name = self._get_container_name_display()
        return f"Uptime {display_name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return getattr(self, '_state', STATE_UNKNOWN)

    @property
    def icon(self):
        return "mdi:clock-outline"

    async def async_update(self):
        """Update the sensor state."""
        try:
            container_info = await self.coordinator.api.get_container_info(self.coordinator.endpoint_id, self.container_id)
            if container_info:
                started_at = container_info["State"]["StartedAt"]
                if started_at and started_at != "0001-01-01T00:00:00Z":
                    # Convert ISO timestamp to human readable format
                    from datetime import datetime
                    try:
                        dt = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                        # Format as relative time (e.g., "2 days ago")
                        from datetime import timezone
                        now = datetime.now(timezone.utc)
                        diff = now - dt.replace(tzinfo=timezone.utc)
                        
                        if diff.days > 0:
                            self._state = f"{diff.days} days ago"
                        elif diff.seconds > 3600:
                            hours = diff.seconds // 3600
                            self._state = f"{hours} hours ago"
                        elif diff.seconds > 60:
                            minutes = diff.seconds // 60
                            self._state = f"{minutes} minutes ago"
                        else:
                            self._state = "Just started"
                    except:
                        # Fallback to original format if parsing fails
                        self._state = started_at
                else:
                    self._state = "Not started"
            else:
                self._state = STATE_UNKNOWN
        except Exception as e:
            _LOGGER.warning("Failed to get uptime for %s: %s", self.name, e)
            self._state = STATE_UNKNOWN

class ContainerImageSensor(BaseContainerEntity, SensorEntity):
    """Sensor for container image."""

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
        return getattr(self, '_state', STATE_UNKNOWN)

    @property
    def icon(self):
        return "mdi:docker"

    async def async_update(self):
        """Update the sensor state."""
        try:
            container_info = await self.coordinator.api.get_container_info(self.coordinator.endpoint_id, self.container_id)
            if container_info:
                self._state = container_info.get("Config", {}).get("Image", STATE_UNKNOWN)
            else:
                self._state = STATE_UNKNOWN
        except Exception as e:
            _LOGGER.warning("Failed to get image for %s: %s", self.name, e)
            self._state = STATE_UNKNOWN

class ContainerCurrentVersionSensor(BaseContainerEntity, SensorEntity):
    """Sensor for container current version."""

    @property
    def entity_type(self) -> str:
        return "current_version"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        display_name = self._get_container_name_display()
        return f"Version {display_name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return getattr(self, '_state', STATE_UNKNOWN)

    @property
    def icon(self):
        return "mdi:tag-text"

    async def async_update(self):
        """Update the sensor state."""
        try:
            container_info = await self.coordinator.api.get_container_info(self.coordinator.endpoint_id, self.container_id)
            if container_info:
                image_id = container_info.get("Image")
                if image_id:
                    # Get image details to extract version info
                    image_data = await self.coordinator.api.get_image_info(self.coordinator.endpoint_id, image_id)
                    if image_data:
                        version = self.coordinator.api.extract_version_from_image(image_data)
                        self._state = version
                    else:
                        self._state = STATE_UNKNOWN
                else:
                    self._state = STATE_UNKNOWN
            else:
                self._state = STATE_UNKNOWN
        except Exception as e:
            _LOGGER.warning("Failed to get current version for %s: %s", self.name, e)
            self._state = STATE_UNKNOWN

class ContainerAvailableVersionSensor(BaseContainerEntity, SensorEntity):
    """Sensor for container available version."""

    @property
    def entity_type(self) -> str:
        return "available_version"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        display_name = self._get_container_name_display()
        return f"Available {display_name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return getattr(self, '_state', STATE_UNKNOWN)

    @property
    def icon(self):
        return "mdi:tag-plus"

    async def async_update(self):
        """Update the sensor state."""
        try:
            container_info = await self.coordinator.api.get_container_info(self.coordinator.endpoint_id, self.container_id)
            if container_info:
                image_name = container_info.get("Config", {}).get("Image")
                if image_name:
                    # Get available version from registry
                    available_version = await self.coordinator.api.get_available_version(self.coordinator.endpoint_id, image_name)
                    self._state = available_version
                else:
                    self._state = STATE_UNKNOWN
            else:
                self._state = STATE_UNKNOWN
        except Exception as e:
            _LOGGER.warning("Failed to get available version for %s: %s", self.name, e)
            self._state = STATE_UNKNOWN