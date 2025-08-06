import logging
from homeassistant.components.switch import SwitchEntity
from .const import DOMAIN
from .portainer_api import PortainerAPI

_LOGGER = logging.getLogger(__name__)
_LOGGER.info("Loaded Portainer switch integration.")

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

    switches = []
    for container in containers:
        name = container.get("Names", ["unknown"])[0].strip("/")
        container_id = container["Id"]
        state = container.get("State", "unknown")
        switches.append(ContainerSwitch(name, state, api, endpoint_id, container_id))

    async_add_entities(switches, update_before_add=True)

class ContainerSwitch(SwitchEntity):
    """Switch to start/stop a Docker container."""

    def __init__(self, name, state, api, endpoint_id, container_id):
        self._attr_name = f"{name} Switch"
        self._container_name = name
        self._state = state == "running"
        self._api = api
        self._endpoint_id = endpoint_id
        self._container_id = container_id
        self._attr_unique_id = f"{container_id}_switch"
        self._available = True

    @property
    def is_on(self):
        return self._state is True

    @property
    def available(self):
        return self._available

    @property
    def icon(self):
        return "mdi:power"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._container_id)},
            "name": self._container_name,
            "manufacturer": "Docker via Portainer",
            "model": "Docker Container",
            "configuration_url": f"{self._api.base_url}/#!/containers/{self._container_id}/details",
        }

    async def async_turn_on(self, **kwargs):
        """Start the Docker container."""
        success = await self._api.start_container(self._endpoint_id, self._container_id)
        if success:
            self._state = True
            self._available = True
        else:
            self._available = False
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Stop the Docker container."""
        success = await self._api.stop_container(self._endpoint_id, self._container_id)
        if success:
            self._state = False
            self._available = True
        else:
            self._available = False
        self.async_write_ha_state()

    async def async_update(self):
        """Update the current status of the container."""
        try:
            containers = await self._api.get_containers(self._endpoint_id)
            for container in containers:
                if container["Id"] == self._container_id:
                    self._state = container.get("State") == "running"
                    self._available = True
                    return
            self._state = False
            self._available = False
        except Exception as e:
            _LOGGER.error("Failed to update status for %s: %s", self._container_name, e)
            self._available = False
