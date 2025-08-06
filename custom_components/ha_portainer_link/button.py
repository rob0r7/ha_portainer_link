import logging
from homeassistant.components.button import ButtonEntity
from .const import DOMAIN
from .portainer_api import PortainerAPI

_LOGGER = logging.getLogger(__name__)
_LOGGER.info("Loaded Portainer button integration.")

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

    buttons = []
    for container in containers:
        name = container.get("Names", ["unknown"])[0].strip("/")
        container_id = container["Id"]
        buttons.append(RestartContainerButton(name, api, endpoint_id, container_id))

    async_add_entities(buttons)

class RestartContainerButton(ButtonEntity):
    """Button to restart a Docker container."""

    def __init__(self, name, api, endpoint_id, container_id):
        self._attr_name = f"{name} Restart"
        self._container_name = name
        self._api = api
        self._endpoint_id = endpoint_id
        self._container_id = container_id
        self._attr_unique_id = f"{container_id}_restart"

    @property
    def icon(self):
        return "mdi:restart"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._container_id)},
            "name": self._container_name,
            "manufacturer": "Docker via Portainer",
            "model": "Docker Container",
            "configuration_url": f"{self._api.base_url}/#!/containers/{self._container_id}/details",
        }

    async def async_press(self) -> None:
        """Restart the Docker container."""
        await self._api.restart_container(self._endpoint_id, self._container_id)
