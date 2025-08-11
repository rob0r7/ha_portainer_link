import logging
import hashlib
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers import entity_registry as er
from .const import DOMAIN
from .portainer_api import PortainerAPI

_LOGGER = logging.getLogger(__name__)
_LOGGER.info("Loaded Portainer binary sensor integration.")


def _merge_options(data, options):
    merged = dict(data)
    if options:
        merged.update(options)
    return merged


def _get_host_display_name(base_url):
    """Extract a clean host name from the base URL for display purposes."""
    # Remove protocol and common ports
    host = base_url.replace("https://", "").replace("http://", "")
    # Remove trailing slash if present
    host = host.rstrip("/")
    # Remove common ports
    for port in [":9000", ":9443", ":80", ":443"]:
        if host.endswith(port):
            host = host[:-len(port)]

    # If the host is an IP address, keep it as is
    # If it's a domain, try to extract a meaningful name
    if host.replace('.', '').replace('-', '').replace('_', '').isdigit():
        # It's an IP address, keep as is
        return host
    else:
        # It's a domain, extract the main part
        parts = host.split('.')
        if len(parts) >= 2:
            # Use the main domain part (e.g., "portainer" from "portainer.example.com")
            return parts[0]
        else:
            return host


def _get_host_hash(base_url):
    """Generate a short hash of the host URL for unique identification."""
    return hashlib.md5(base_url.encode()).hexdigest()[:8]


def _build_stable_unique_id(entry_id, endpoint_id, container_name, stack_info, suffix):
    if stack_info.get("is_stack_container"):
        stack_name = stack_info.get("stack_name", "unknown")
        service_name = stack_info.get("service_name", container_name)
        base = f"{stack_name}_{service_name}"
    else:
        base = container_name
    sanitized = base.replace('-', '_').replace(' ', '_').replace('/', '_')
    return f"entry_{entry_id}_endpoint_{endpoint_id}_{sanitized}_{suffix}"


async def async_setup_entry(hass, entry, async_add_entities):
    config = _merge_options(entry.data, entry.options)
    host = config["host"]
    username = config.get("username")
    password = config.get("password")
    api_key = config.get("api_key")
    endpoint_id = config["endpoint_id"]
    entry_id = entry.entry_id

    enable_update_sensors = config.get("enable_update_sensors", False)
    if not enable_update_sensors:
        _LOGGER.info("Update sensors disabled by options; skipping binary_sensor setup for entry %s", entry_id)
        async_add_entities([])
        return

    api = PortainerAPI(host, username, password, api_key)
    await api.initialize()
    containers = await api.get_containers(endpoint_id)

    # Migrate old unique_ids to stable unique_ids
    try:
        er_registry = er.async_get(hass)
        for container in containers:
            name = container.get("Names", ["unknown"])[0].strip("/")
            container_id = container["Id"]
            container_info = await api.inspect_container(endpoint_id, container_id)
            stack_info = api.get_container_stack_info(container_info) if container_info else {"is_stack_container": False}
            old_uid = f"entry_{entry_id}_endpoint_{endpoint_id}_{container_id}_update_available"
            new_uid = _build_stable_unique_id(entry_id, endpoint_id, name, stack_info, "update_available")
            if old_uid != new_uid:
                ent_id = er_registry.async_get_entity_id("binary_sensor", DOMAIN, old_uid)
                if ent_id:
                    try:
                        er_registry.async_update_entity(ent_id, new_unique_id=new_uid)
                        _LOGGER.debug("Migrated %s unique_id: %s -> %s", ent_id, old_uid, new_uid)
                    except Exception as e:
                        _LOGGER.debug("Could not migrate %s: %s", ent_id, e)
    except Exception as e:
        _LOGGER.debug("Binary sensor registry migration skipped/failed: %s", e)

    entities = []
    for container in containers:
        name = container.get("Names", ["unknown"])[0].strip("/")
        container_id = container["Id"]

        # Get container inspection data to determine if it's part of a stack
        container_info = await api.inspect_container(endpoint_id, container_id)
        stack_info = api.get_container_stack_info(container_info) if container_info else {"is_stack_container": False}

        # Create binary sensors for all containers - they will all belong to the same stack device if they're in a stack
        entities.append(ContainerUpdateAvailableSensor(name, api, endpoint_id, container_id, stack_info, entry_id))

    async_add_entities(entities, update_before_add=True)


class ContainerUpdateAvailableSensor(BinarySensorEntity):
    """Binary sensor representing if a container has updates available."""

    def __init__(self, name, api, endpoint_id, container_id, stack_info, entry_id):
        self._attr_name = f"{name} Update Available"
        self._container_name = name
        self._api = api
        self._endpoint_id = endpoint_id
        self._container_id = container_id
        self._stack_info = stack_info
        self._entry_id = entry_id
        self._attr_unique_id = _build_stable_unique_id(entry_id, endpoint_id, name, stack_info, "update_available")
        self._attr_is_on = False

    async def _find_current_container_id(self):
        try:
            containers = await self._api.get_containers(self._endpoint_id)
            if not containers:
                return None
            if self._stack_info.get("is_stack_container"):
                expected_stack = self._stack_info.get("stack_name")
                expected_service = self._stack_info.get("service_name")
                for container in containers:
                    labels = container.get("Labels", {}) or {}
                    if (
                        labels.get("com.docker.compose.project") == expected_stack
                        and labels.get("com.docker.compose.service") == expected_service
                    ):
                        return container.get("Id")
            for container in containers:
                names = container.get("Names", []) or []
                if not names:
                    continue
                name = names[0].strip("/")
                if name == self._container_name:
                    return container.get("Id")
        except Exception:
            return None
        return None

    async def _ensure_container_bound(self) -> None:
        try:
            info = await self._api.get_container_info(self._endpoint_id, self._container_id)
            if not info or not isinstance(info, dict) or not info.get("Id"):
                new_id = await self._find_current_container_id()
                if new_id and new_id != self._container_id:
                    self._container_id = new_id
        except Exception:
            new_id = await self._find_current_container_id()
            if new_id and new_id != self._container_id:
                self._container_id = new_id

    @property
    def icon(self):
        return "mdi:update" if self._attr_is_on else "mdi:update-disabled"

    @property
    def device_info(self):
        host_name = _get_host_display_name(self._api.base_url)
        host_hash = _get_host_hash(self._api.base_url)

        if self._stack_info.get("is_stack_container"):
            # For stack containers, use the stack as the device
            stack_name = self._stack_info.get("stack_name", "unknown_stack")
            # Use a more robust identifier that includes the entry_id, host hash, and host name to prevent duplicates
            device_id = f"entry_{self._entry_id}_endpoint_{self._endpoint_id}_stack_{stack_name}_{host_hash}_{host_name.replace('.', '_').replace(':', '_')}"
            return {
                "identifiers": {(DOMAIN, device_id)},
                "name": f"Stack: {stack_name} ({host_name})",
                "manufacturer": "Docker via Portainer",
                "model": "Docker Stack",
                "configuration_url": f"{self._api.base_url}/#!/stacks/{stack_name}",
            }
        else:
            # For standalone containers, use the container as the device
            device_id = f"entry_{self._entry_id}_endpoint_{self._endpoint_id}_container_{self._container_id}_{host_hash}_{host_name.replace('.', '_').replace(':', '_')}"
            return {
                "identifiers": {(DOMAIN, device_id)},
                "name": f"{self._container_name} ({host_name})",
                "manufacturer": "Docker via Portainer",
                "model": "Docker Container",
                "configuration_url": f"{self._api.base_url}/#!/containers/{self._container_id}/details",
            }

    async def async_update(self):
        """Update the update availability status."""
        try:
            await self._ensure_container_bound()
            has_update = await self._api.check_image_updates(self._endpoint_id, self._container_id)
            self._attr_is_on = has_update
        except Exception as e:
            _LOGGER.warning("Failed to check update availability for %s: %s", self._attr_name, e)
            self._attr_is_on = False
