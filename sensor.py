import logging
from homeassistant.helpers.entity import Entity
from homeassistant.const import STATE_UNKNOWN
from .const import DOMAIN
from .portainer_api import PortainerAPI


_LOGGER = logging.getLogger(__name__)
_LOGGER.warning("Portainer sensor.py wurde erfolgreich geladen")


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up Portainer container sensors."""
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
    containers = api.get_containers(endpoint_id)

    entities = []
    for container in containers:
        if not container.get("Names"):
            continue
        name = container["Names"][0].strip("/")
        state = container.get("State", "unknown")
        entities.append(ContainerStatusSensor(name, state))

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
