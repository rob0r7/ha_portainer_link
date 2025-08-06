import logging
from homeassistant.helpers.entity import Entity
from homeassistant.const import STATE_UNKNOWN
from .const import DOMAIN
from .portainer_api import PortainerAPI

_LOGGER = logging.getLogger(__name__)
_LOGGER.warning("Portainer sensor.py wurde erfolgreich geladen")

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    conf = hass.data.get(DOMAIN)
    if not conf:
        _LOGGER.error("No config data available in sensor")
        return

    host = conf["host"]
    username = conf.get("username")
    password = conf.get("password")
    api_key = conf.get("api_key")
    endpoint_id = conf["endpoint_id"]

    api = PortainerAPI(host, username, password, api_key)
    await api.initialize()
    containers = await api.get_containers(endpoint_id)

    entities = []
    for container in containers:
        if not container.get("Names"):
            continue

        name = container["Names"][0].strip("/")
        container_id = container["Id"]
        state = container.get("State", "unknown")

        entities.append(ContainerStatusSensor(name, state))
        entities.append(ContainerCPUSensor(name, api, endpoint_id, container_id))
        entities.append(ContainerMemorySensor(name, api, endpoint_id, container_id))

    async_add_entities(entities, update_before_add=True)

class ContainerStatusSensor(Entity):
    def __init__(self, name, state):
        self._name = f"{name}_status"
        self._state = state

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return f"sensor_{self._name}"

    @property
    def state(self):
        return self._state or STATE_UNKNOWN

    @property
    def icon(self):
        if self._state == "running":
            return "mdi:docker"
        elif self._state == "exited":
            return "mdi:close-circle"
        elif self._state == "paused":
            return "mdi:pause-circle"
        else:
            return "mdi:help-circle"

class ContainerCPUSensor(Entity):
    def __init__(self, name, api, endpoint_id, container_id):
        self._name = f"{name}_cpu"
        self._api = api
        self._endpoint_id = endpoint_id
        self._container_id = container_id
        self._state = STATE_UNKNOWN

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return f"sensor_{self._name}"

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
        _LOGGER.debug("Raw CPU stats for %s: %s", self._name, stats)
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
            _LOGGER.warning("Failed to parse CPU stats for %s: %s", self._name, e)
            self._state = 0.0

class ContainerMemorySensor(Entity):
    def __init__(self, name, api, endpoint_id, container_id):
        self._name = f"{name}_memory"
        self._api = api
        self._endpoint_id = endpoint_id
        self._container_id = container_id
        self._state = STATE_UNKNOWN

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return f"sensor_{self._name}"

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
            _LOGGER.warning("Failed to parse memory stats for %s: %s", self._name, e)
            self._state = STATE_UNKNOWN
