import logging
from homeassistant.components.switch import SwitchEntity
from .const import DOMAIN
from .portainer_api import PortainerAPI

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up Portainer container switches."""
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
    containers = api.get_containers(endpoint_id)

    entities = []
    for container in containers:
        if not container.get("Names"):
            continue
        name = container["Names"][0].strip("/")
        container_id = container["Id"]
        state = container["State"]
        entities.append(DockerContainerSwitch(name, container_id, endpoint_id, api, state))

    async_add_entities(entities, update_before_add=True)

class DockerContainerSwitch(SwitchEntity):
    def __init__(self, name, container_id, endpoint_id, api: PortainerAPI, state):
        self._name = name
        self._container_id = container_id
        self._endpoint_id = endpoint_id
        self._api = api
        self._is_on = state == "running"

    @property
    def name(self):
        return f"{self._name}"

    @property
    def unique_id(self):
        return f"switch_{self._container_id}"

    @property
    def is_on(self):
        return self._is_on

    @property
    def icon(self):
        return "mdi:docker"

    def turn_on(self, **kwargs):
        if self._api.start_container(self._endpoint_id, self._container_id):
            self._is_on = True

    def turn_off(self, **kwargs):
        if self._api.stop_container(self._endpoint_id, self._container_id):
            self._is_on = False

    def update(self):
        data = self._api.inspect_container(self._endpoint_id, self._container_id)
        if data:
            self._is_on = data.get("State", {}).get("Running", False)
