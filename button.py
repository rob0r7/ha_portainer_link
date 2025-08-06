import logging
from homeassistant.components.button import ButtonEntity
from .const import DOMAIN
from .portainer_api import PortainerAPI

_LOGGER = logging.getLogger(__name__)
_LOGGER.warning("Portainer button.py wurde erfolgreich geladen")

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    conf = hass.data.get(DOMAIN)
    if not conf:
        _LOGGER.error("No config data available in button")
        return

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
        if not container.get("Names"):
            continue
        name = container["Names"][0].strip("/")
        container_id = container["Id"]
        _LOGGER.warning("→ Restart-Button für Container: /%s", name)
        buttons.append(PortainerRestartButton(name, container_id, api, endpoint_id))

    async_add_entities(buttons)

class PortainerRestartButton(ButtonEntity):
    def __init__(self, name, container_id, api, endpoint_id):
        self._attr_name = f"{name}_restart"
        self._container_id = container_id
        self._api = api
        self._endpoint_id = endpoint_id
        self._attr_unique_id = f"restart_{container_id}"
        self._attr_icon = "mdi:restart"

    async def async_press(self) -> None:
        success = await self._api.restart_container(self._endpoint_id, self._container_id)
        if success:
            _LOGGER.info("Container %s erfolgreich neugestartet", self._container_id)
        else:
            _LOGGER.error("Fehler beim Neustart von Container %s", self._container_id)
