import logging
from homeassistant.components.switch import SwitchEntity
from .const import DOMAIN
from .portainer_api import PortainerAPI

_LOGGER = logging.getLogger(__name__)
_LOGGER.warning("Portainer switch.py wurde erfolgreich geladen")

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up Portainer switches for containers."""
    conf = hass.data.get(DOMAIN)
    if not conf:
        _LOGGER.error("No config data available in switch")
        return

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
        _LOGGER.warning("→ Switch erstellt für Container: /%s", name)
        switches.append(PortainerContainerSwitch(name, container_id, state, api, endpoint_id))

    async_add_entities(switches, update_before_add=True)

class PortainerContainerSwitch(SwitchEntity):
    def __init__(self, name, container_id, state, api, endpoint_id):
        self._name = name
        self._container_id = container_id
        self._state = state
        self._api = api
        self._endpoint_id = endpoint_id

    @property
    def name(self):
        return f"{self._name}_switch"

    @property
    def unique_id(self):
        return f"switch_{self._container_id}"

    @property
    def is_on(self):
        return self._state == "running"

    async def async_turn_on(self, **kwargs):
        success = await self._api.start_container(self._endpoint_id, self._container_id)
        if success:
            self._state = "running"
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        success = await self._api.stop_container(self._endpoint_id, self._container_id)
        if success:
            self._state = "exited"
            self.async_write_ha_state()

    async def async_update(self):
        container_info = await self._api.inspect_container(self._endpoint_id, self._container_id)
        if container_info:
            self._state = container_info.get("State", {}).get("Status", "unknown")
