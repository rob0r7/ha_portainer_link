import logging
from homeassistant.helpers.entity import Entity
from homeassistant.const import STATE_UNKNOWN
from .const import DOMAIN
from .portainer_api import PortainerAPI

_LOGGER = logging.getLogger(__name__)
_LOGGER.info("Loaded Portainer sensor integration.")

async def async_setup_entry(hass, entry, async_add_entities):
    config = entry.data
    host = config["host"]
    username = config.get("username")
    password = config.get("password")
    api_key = config.get("api_key")
    endpoint_id = config["endpoint_id"]

    api = PortainerAPI(host, username, password, api_key)
    await api.initialize()
    containers = await api.get_containers(endpoint_id)

    entities = []
    for container in containers:
        name = container.get("Names", ["unknown"])[0].strip("/")
        container_id = container["Id"]
        state = container.get("State", STATE_UNKNOWN)

        entities.append(ContainerStatusSensor(name, state, api, container_id))
        entities.append(ContainerCPUSensor(name, api, endpoint_id, container_id))
        entities.append(ContainerMemorySensor(name, api, endpoint_id, container_id))
        entities.append(ContainerUptimeSensor(name, api, endpoint_id, container_id))
        entities.append(ContainerImageSensor(name, container, api, container_id))

    async_add_entities(entities, update_before_add=True)

class BaseContainerSensor(Entity):
    """Base class for all container sensors."""

    def __init__(self, container_name, container_id, api):
        self._container_name = container_name
        self._container_id = container_id
        self._api = api

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._container_id)},
            "name": self._container_name,
            "manufacturer": "Docker via Portainer",
            "model": "Docker Container",
            "configuration_url": f"{self._api.base_url}/#!/containers/{self._container_id}/details",
        }

class ContainerStatusSensor(BaseContainerSensor):
    """Sensor representing the status of a Docker container."""

    def __init__(self, name, state, api, container_id):
        super().__init__(name, container_id, api)
        self._attr_name = f"{name} Status"
        self._attr_unique_id = f"{container_id}_status"
        self._state = state

    @property
    def state(self):
        return self._state or STATE_UNKNOWN

    @property
    def icon(self):
        return {
            "running": "mdi:docker",
            "exited": "mdi:close-circle",
            "paused": "mdi:pause-circle",
        }.get(self._state, "mdi:help-circle")

class ContainerCPUSensor(BaseContainerSensor):
    """Sensor representing CPU usage of a Docker container."""

    def __init__(self, name, api, endpoint_id, container_id):
        super().__init__(name, container_id, api)
        self._attr_name = f"{name} CPU Usage"
        self._attr_unique_id = f"{container_id}_cpu_usage"
        self._endpoint_id = endpoint_id
        self._state = STATE_UNKNOWN

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        return "%"

    @property
    def icon(self):
        return "mdi:cpu-64-bit"

    async def async_update(self):
        stats = await self._api.get_container_stats(self._endpoint_id, self._container_id)
        try:
            cpu_usage = stats["cpu_stats"]["cpu_usage"]["total_usage"]
            precpu_usage = stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_cpu = stats["cpu_stats"]["system_cpu_usage"]
            pre_system_cpu = stats["precpu_stats"]["system_cpu_usage"]

            cpu_delta = cpu_usage - precpu_usage
            system_delta = system_cpu - pre_system_cpu
            cpu_count = stats.get("cpu_stats", {}).get("online_cpus", 1)

            usage = (cpu_delta / system_delta) * cpu_count * 100.0 if system_delta > 0 else 0
            self._state = round(usage, 2)
        except Exception as e:
            _LOGGER.warning("Failed to parse CPU stats for %s: %s", self._attr_name, e)
            self._state = STATE_UNKNOWN

class ContainerMemorySensor(BaseContainerSensor):
    """Sensor representing memory usage of a Docker container."""

    def __init__(self, name, api, endpoint_id, container_id):
        super().__init__(name, container_id, api)
        self._attr_name = f"{name} Memory Usage"
        self._attr_unique_id = f"{container_id}_memory_usage"
        self._endpoint_id = endpoint_id
        self._state = STATE_UNKNOWN

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        return "MB"

    @property
    def icon(self):
        return "mdi:memory"

    async def async_update(self):
        stats = await self._api.get_container_stats(self._endpoint_id, self._container_id)
        try:
            mem_bytes = stats["memory_stats"]["usage"]
            self._state = round(mem_bytes / (1024 * 1024), 2)
        except Exception as e:
            _LOGGER.warning("Failed to parse memory stats for %s: %s", self._attr_name, e)
            self._state = STATE_UNKNOWN

class ContainerUptimeSensor(BaseContainerSensor):
    """Sensor representing uptime of a Docker container."""

    def __init__(self, name, api, endpoint_id, container_id):
        super().__init__(name, container_id, api)
        self._attr_name = f"{name} Uptime"
        self._attr_unique_id = f"{container_id}_uptime"
        self._endpoint_id = endpoint_id
        self._state = STATE_UNKNOWN

    @property
    def state(self):
        return self._state

    @property
    def icon(self):
        return "mdi:clock-outline"

    async def async_update(self):
        container_info = await self._api.get_container_info(self._endpoint_id, self._container_id)
        try:
            self._state = container_info["State"]["StartedAt"]
        except Exception as e:
            _LOGGER.warning("Failed to get uptime for %s: %s", self._attr_name, e)
            self._state = STATE_UNKNOWN

class ContainerImageSensor(BaseContainerSensor):
    """Sensor representing Docker image of a container."""

    def __init__(self, name, container_data, api, container_id):
        super().__init__(name, container_id, api)
        self._attr_name = f"{name} Image"
        self._attr_unique_id = f"{container_id}_image"
        self._state = container_data.get("Image", STATE_UNKNOWN)

    @property
    def state(self):
        return self._state

    @property
    def icon(self):
        return "mdi:docker"
