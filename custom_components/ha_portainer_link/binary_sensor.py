import logging
from homeassistant.components.binary_sensor import BinarySensorEntity
from .const import DOMAIN
from .portainer_api import PortainerAPI

_LOGGER = logging.getLogger(__name__)
_LOGGER.info("Loaded Portainer binary sensor integration.")

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
        entities.append(ContainerUpdateAvailableSensor(name, api, endpoint_id, container_id))

    async_add_entities(entities, update_before_add=True)


class ContainerUpdateAvailableSensor(BinarySensorEntity):
    """Binary sensor representing if a container has updates available."""

    def __init__(self, name, api, endpoint_id, container_id):
        self._attr_name = f"{name} Update Available"
        self._container_name = name
        self._api = api
        self._endpoint_id = endpoint_id
        self._container_id = container_id
        self._attr_unique_id = f"{container_id}_update_available"
        self._attr_is_on = False

    @property
    def icon(self):
        return "mdi:update" if self._attr_is_on else "mdi:update-disabled"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._container_id)},
            "name": self._container_name,
            "manufacturer": "Docker via Portainer",
            "model": "Docker Container",
            "configuration_url": f"{self._api.base_url}/#!/containers/{self._container_id}/details",
        }

    async def async_update(self):
        """Update the update availability status."""
        try:
            has_update = await self._api.check_image_updates(self._endpoint_id, self._container_id)
            self._attr_is_on = has_update
        except Exception as e:
            _LOGGER.warning("Failed to check update availability for %s: %s", self._attr_name, e)
            self._attr_is_on = False
