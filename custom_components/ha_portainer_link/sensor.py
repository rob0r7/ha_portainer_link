import logging
from homeassistant.const import STATE_UNKNOWN
from homeassistant.components.sensor import SensorEntity

from .const import DOMAIN, CONF_ENABLE_RESOURCE_SENSORS, CONF_ENABLE_VERSION_SENSORS, DEFAULT_ENABLE_RESOURCE_SENSORS, DEFAULT_ENABLE_VERSION_SENSORS
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
    
    # Check if sensors are enabled
    resource_sensors_enabled = config.get(CONF_ENABLE_RESOURCE_SENSORS, DEFAULT_ENABLE_RESOURCE_SENSORS)
    version_sensors_enabled = config.get(CONF_ENABLE_VERSION_SENSORS, DEFAULT_ENABLE_VERSION_SENSORS)
    
    _LOGGER.info("📊 Sensor configuration: Resource sensors=%s, Version sensors=%s", 
                 resource_sensors_enabled, version_sensors_enabled)
    
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

    _LOGGER.info("✅ Created %d sensor entities (Status: always, Resource: %s, Version: %s)", 
                 len(entities), resource_sensors_enabled, version_sensors_enabled)
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

            # Get container stats
            stats = await self.coordinator.api.get_container_stats(
                self.coordinator.endpoint_id, self.container_id
            )
            
            if stats and "read" in stats:
                # Calculate uptime from the read timestamp
                import time
                current_time = time.time()
                start_time = stats["read"]
                uptime_seconds = current_time - start_time
                
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
            else:
                self._state = STATE_UNKNOWN
                
        except Exception as e:
            _LOGGER.error("❌ Error updating uptime sensor for container %s: %s", self.container_id, e)
            self._state = STATE_UNKNOWN

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

class ContainerAvailableVersionSensor(BaseContainerEntity, SensorEntity):
    """Sensor for container available version."""

    @property
    def entity_type(self) -> str:
        return "available_version"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        display_name = self._get_container_name_display()
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

            # Get container inspection data
            container_info = await self.coordinator.api.inspect_container(
                self.coordinator.endpoint_id, self.container_id
            )
            
            if container_info and "Config" in container_info:
                image_name = container_info["Config"].get("Image", "")
                if image_name:
                    # Get available version from registry
                    available_version = await self.coordinator.api.get_available_version(
                        self.coordinator.endpoint_id, image_name
                    )
                    self._state = available_version
                else:
                    self._state = STATE_UNKNOWN
            else:
                self._state = STATE_UNKNOWN
                
        except Exception as e:
            _LOGGER.error("❌ Error updating available version sensor for container %s: %s", self.container_id, e)
            self._state = STATE_UNKNOWN