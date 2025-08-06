import logging
from homeassistant.components.switch import SwitchEntity
from .const import DOMAIN
from .portainer_api import PortainerAPI

_LOGGER = logging.getLogger(__name__)
_LOGGER.warning("Portainer switch.py wurde erfolgreich geladen")

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
        if not container.get("Names"):
            continue
        name = container["Names"][0].strip("/")
        container_id = container["Id"]
        state = container.get("State", "unknown")
        switches.append(ContainerSwitch(name, state, api, endpoint_id, container_id))

    async_add_entities(switches, update_before_add=True)

class ContainerSwitch(SwitchEntity):
    def __init__(self, name, state, api, endpoint_id, container_id):
        self._name = f"{name}_switch"
        self._container_name = name
        self._state = state == "running"
        self._api = api
        self._endpoint_id = endpoint_id
        self._container_id = container_id

    @property
    def name(self):
        return self._name

    @property
    def is_on(self):
        return self._state

    @property
    def unique_id(self):
        return f"switch_{self._name}"

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
        success = await self._api.start_container(self._endpoint_id, self._container_id)
        if success:
            self._state = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        success = await self._api.stop_container(self._endpoint_id, self._container_id)
        if success:
            self._state = False
            self.async_write_ha_state()
