import logging
import hashlib
from homeassistant.helpers.entity import Entity
from homeassistant.const import STATE_UNKNOWN
from homeassistant.helpers import entity_registry as er
from .const import DOMAIN
from .portainer_api import PortainerAPI

_LOGGER = logging.getLogger(__name__)
_LOGGER.info("Loaded Portainer sensor integration.")


def _merge_options(data, options):
    merged = dict(data)
    if options:
        merged.update(options)
    return merged


def _build_stable_unique_id(entry_id, endpoint_id, container_name, stack_info, suffix):
    if stack_info.get("is_stack_container"):
        stack_name = stack_info.get("stack_name", "unknown")
        service_name = stack_info.get("service_name", container_name)
        base = f"{stack_name}_{service_name}"
    else:
        base = container_name
    sanitized = base.replace('-', '_').replace(' ', '_').replace('/', '_')
    return f"entry_{entry_id}_endpoint_{endpoint_id}_{sanitized}_{suffix}"


def _get_host_display_name(base_url):
    """Extract a clean host name from the base URL for display purposes."""
    # Remove protocol and common ports
    host = base_url.replace("https://", "http://").replace("http://", "")
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


async def async_setup_entry(hass, entry, async_add_entities):
    config = _merge_options(entry.data, entry.options)
    host = config["host"]
    username = config.get("username")
    password = config.get("password")
    api_key = config.get("api_key")
    endpoint_id = config["endpoint_id"]
    entry_id = entry.entry_id

    enable_resource_sensors = config.get("enable_resource_sensors", False)
    enable_version_sensors = config.get("enable_version_sensors", False)

    _LOGGER.info("🚀 Setting up HA Portainer Link sensors for entry %s (endpoint %s)", entry_id, endpoint_id)
    _LOGGER.info("📍 Portainer host: %s", host)

    # Log the extracted host name for debugging
    host_display_name = _get_host_display_name(host)
    _LOGGER.info("🏷️ Extracted host display name: %s", host_display_name)

    api = PortainerAPI(host, username, password, api_key)
    await api.initialize()
    containers = await api.get_containers(endpoint_id)

    _LOGGER.info("📦 Found %d containers to process", len(containers))

    entities = []
    stack_containers_count = 0
    standalone_containers_count = 0

    # Migrate existing entities to stable unique_ids to avoid breaking automations
    try:
        er_registry = er.async_get(hass)
        for container in containers:
            name = container.get("Names", ["unknown"])[0].strip("/")
            container_id = container["Id"]
            container_info = await api.inspect_container(endpoint_id, container_id)
            stack_info = api.get_container_stack_info(container_info) if container_info else {"is_stack_container": False}
            # Old unique_id suffixes and new stable mapping
            suffixes = [
                ("status", "sensor"),
                ("cpu_usage", "sensor"),
                ("memory_usage", "sensor"),
                ("uptime", "sensor"),
                ("image", "sensor"),
                ("current_version", "sensor"),
                ("available_version", "sensor"),
            ]
            for suffix, domain_name in suffixes:
                old_uid = f"entry_{entry_id}_endpoint_{endpoint_id}_{container_id}_{suffix}"
                new_uid = _build_stable_unique_id(entry_id, endpoint_id, name, stack_info, suffix)
                if old_uid == new_uid:
                    continue
                ent_id = er_registry.async_get_entity_id(domain_name, DOMAIN, old_uid)
                if ent_id:
                    try:
                        er_registry.async_update_entity(ent_id, new_unique_id=new_uid)
                        _LOGGER.debug("Migrated %s unique_id: %s -> %s", ent_id, old_uid, new_uid)
                    except Exception as e:
                        _LOGGER.debug("Could not migrate %s: %s", ent_id, e)
    except Exception as e:
        _LOGGER.debug("Entity registry migration skipped/failed: %s", e)

    for container in containers:
        name = container.get("Names", ["unknown"])[0].strip("/")
        container_id = container["Id"]
        state = container.get("State", STATE_UNKNOWN)

        _LOGGER.debug("🔍 Processing container: %s (ID: %s, State: %s)", name, container_id, state)

        # Get container inspection data to determine if it's part of a stack
        container_info = await api.inspect_container(endpoint_id, container_id)
        stack_info = api.get_container_stack_info(container_info) if container_info else {"is_stack_container": False}

        if stack_info.get("is_stack_container"):
            stack_containers_count += 1
            _LOGGER.info("📋 Container %s is part of stack: %s", name, stack_info.get("stack_name"))
        else:
            standalone_containers_count += 1
            _LOGGER.info("📦 Container %s is standalone", name)

        # Always-on basic sensors
        entities.append(ContainerStatusSensor(name, state, api, endpoint_id, container_id, stack_info, entry_id))
        entities.append(ContainerImageSensor(name, container, api, endpoint_id, container_id, stack_info, entry_id))

        # Optional sensors by toggles
        if enable_resource_sensors:
            entities.append(ContainerCPUSensor(name, api, endpoint_id, container_id, stack_info, entry_id))
            entities.append(ContainerMemorySensor(name, api, endpoint_id, container_id, stack_info, entry_id))
            entities.append(ContainerUptimeSensor(name, api, endpoint_id, container_id, stack_info, entry_id))

        if enable_version_sensors:
            entities.append(ContainerCurrentVersionSensor(name, api, endpoint_id, container_id, stack_info, entry_id))
            entities.append(ContainerAvailableVersionSensor(name, api, endpoint_id, container_id, stack_info, entry_id))

    _LOGGER.info("✅ Created %d entities (%d stack containers, %d standalone containers)",
                len(entities), stack_containers_count, standalone_containers_count)

    async_add_entities(entities, update_before_add=True)


class ContainerStatusSensor(Entity):
    """Sensor representing the status of a Docker container."""

    def __init__(self, name, state, api, endpoint_id, container_id, stack_info, entry_id):
        self._attr_name = f"{name} Status"
        self._container_name = name
        self._state = state
        self._api = api
        self._endpoint_id = endpoint_id
        self._container_id = container_id
        self._stack_info = stack_info
        self._entry_id = entry_id
        self._attr_unique_id = _build_stable_unique_id(entry_id, endpoint_id, name, stack_info, "status")
        self._available = True

    @property
    def icon(self):
        return "mdi:docker"

    @property
    def state(self):
        return self._state

    @property
    def available(self):
        return self._available

    @property
    def device_info(self):
        host_name = _get_host_display_name(self._api.base_url)
        host_hash = _get_host_hash(self._api.base_url)

        if self._stack_info.get("is_stack_container"):
            stack_name = self._stack_info.get("stack_name", "unknown_stack")
            device_id = f"entry_{self._entry_id}_endpoint_{self._endpoint_id}_stack_{stack_name}_{host_hash}_{host_name.replace('.', '_').replace(':', '_')}"
            return {
                "identifiers": {(DOMAIN, device_id)},
                "name": f"Stack: {stack_name} ({host_name})",
                "manufacturer": "Docker via Portainer",
                "model": "Docker Stack",
                "configuration_url": f"{self._api.base_url}/#!/stacks/{stack_name}",
            }
        else:
            device_id = f"entry_{self._entry_id}_endpoint_{self._endpoint_id}_container_{self._container_id}_{host_hash}_{host_name.replace('.', '_').replace(':', '_')}"
            return {
                "identifiers": {(DOMAIN, device_id)},
                "name": f"{self._container_name} ({host_name})",
                "manufacturer": "Docker via Portainer",
                "model": "Docker Container",
                "configuration_url": f"{self._api.base_url}/#!/containers/{self._container_id}/details",
            }


class ContainerCPUSensor(Entity):
    """Sensor representing CPU usage of a Docker container."""

    def __init__(self, name, api, endpoint_id, container_id, stack_info, entry_id):
        self._attr_name = f"{name} CPU Usage"
        self._container_name = name
        self._api = api
        self._endpoint_id = endpoint_id
        self._container_id = container_id
        self._stack_info = stack_info
        self._entry_id = entry_id
        self._attr_unique_id = _build_stable_unique_id(entry_id, endpoint_id, name, stack_info, "cpu_usage")
        self._available = True
        self._state = None

    @property
    def icon(self):
        return "mdi:cpu-64-bit"

    async def async_update(self):
        try:
            stats = await self._api.get_container_stats(self._endpoint_id, self._container_id)
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
            _LOGGER.warning("Failed to get CPU stats for %s: %s", self._attr_name, e)
            self._state = None

    @property
    def state(self):
        return self._state


class ContainerMemorySensor(Entity):
    """Sensor representing memory usage of a Docker container."""

    def __init__(self, name, api, endpoint_id, container_id, stack_info, entry_id):
        self._attr_name = f"{name} Memory Usage"
        self._container_name = name
        self._api = api
        self._endpoint_id = endpoint_id
        self._container_id = container_id
        self._stack_info = stack_info
        self._entry_id = entry_id
        self._attr_unique_id = _build_stable_unique_id(entry_id, endpoint_id, name, stack_info, "memory_usage")
        self._available = True
        self._state = None

    @property
    def icon(self):
        return "mdi:memory"

    async def async_update(self):
        try:
            stats = await self._api.get_container_stats(self._endpoint_id, self._container_id)
            mem_bytes = stats["memory_stats"]["usage"]
            self._state = round(mem_bytes / (1024 * 1024), 2)
        except Exception as e:
            _LOGGER.warning("Failed to parse memory stats for %s: %s", self._attr_name, e)
            self._state = None

    @property
    def state(self):
        return self._state


class ContainerUptimeSensor(Entity):
    """Sensor representing uptime of a Docker container."""

    def __init__(self, name, api, endpoint_id, container_id, stack_info, entry_id):
        self._attr_name = f"{name} Uptime"
        self._container_name = name
        self._api = api
        self._endpoint_id = endpoint_id
        self._container_id = container_id
        self._stack_info = stack_info
        self._entry_id = entry_id
        self._attr_unique_id = _build_stable_unique_id(entry_id, endpoint_id, name, stack_info, "uptime")
        self._available = True
        self._state = None

    @property
    def icon(self):
        return "mdi:clock-outline"

    async def async_update(self):
        try:
            info = await self._api.inspect_container(self._endpoint_id, self._container_id)
            started_at = (info or {}).get("State", {}).get("StartedAt")
            if started_at:
                import datetime
                start_time = datetime.datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                current_time = datetime.datetime.now(datetime.timezone.utc)
                self._state = int((current_time - start_time).total_seconds())
        except Exception as e:
            _LOGGER.warning("Failed to get uptime for %s: %s", self._attr_name, e)
            self._state = None

    @property
    def state(self):
        return self._state


class ContainerImageSensor(Entity):
    """Sensor representing the image of a Docker container."""

    def __init__(self, name, container, api, endpoint_id, container_id, stack_info, entry_id):
        self._attr_name = f"{name} Image"
        self._container_name = name
        self._container = container
        self._api = api
        self._endpoint_id = endpoint_id
        self._container_id = container_id
        self._stack_info = stack_info
        self._entry_id = entry_id
        self._attr_unique_id = _build_stable_unique_id(entry_id, endpoint_id, name, stack_info, "image")
        self._available = True
        self._state = None

    async def async_update(self):
        try:
            info = await self._api.inspect_container(self._endpoint_id, self._container_id)
            if not info:
                self._state = None
                return
            image_name = (info.get("Config", {}) or {}).get("Image")
            self._state = image_name
        except Exception as e:
            _LOGGER.warning("Failed to get image for %s: %s", self._attr_name, e)
            self._state = None

    @property
    def icon(self):
        return "mdi:docker"

    @property
    def state(self):
        return self._state


class ContainerCurrentVersionSensor(Entity):
    """Sensor representing the current version of the container image."""

    def __init__(self, name, api, endpoint_id, container_id, stack_info, entry_id):
        self._attr_name = f"{name} Current Version"
        self._container_name = name
        self._api = api
        self._endpoint_id = endpoint_id
        self._container_id = container_id
        self._stack_info = stack_info
        self._entry_id = entry_id
        self._attr_unique_id = _build_stable_unique_id(entry_id, endpoint_id, name, stack_info, "current_version")
        self._available = True
        self._state = None

    async def async_update(self):
        try:
            info = await self._api.inspect_container(self._endpoint_id, self._container_id)
            if not info:
                self._state = None
                return
            image_id = info.get("Image")
            if image_id:
                image_info = await self._api.get_image_info(self._endpoint_id, image_id)
                if image_info:
                    try:
                        self._state = self._api.extract_version_from_image(image_info)
                    except Exception:
                        self._state = None
        except Exception as e:
            _LOGGER.warning("Failed to get current version for %s: %s", self._attr_name, e)
            self._state = None

    @property
    def icon(self):
        return "mdi:tag"

    @property
    def state(self):
        return self._state


class ContainerAvailableVersionSensor(Entity):
    """Sensor representing the available version of the container image."""

    def __init__(self, name, api, endpoint_id, container_id, stack_info, entry_id):
        self._attr_name = f"{name} Available Version"
        self._container_name = name
        self._api = api
        self._endpoint_id = endpoint_id
        self._container_id = container_id
        self._stack_info = stack_info
        self._entry_id = entry_id
        self._attr_unique_id = _build_stable_unique_id(entry_id, endpoint_id, name, stack_info, "available_version")
        self._available = True
        self._state = None

    async def async_update(self):
        try:
            # Attempt to derive the available version using API helpers
            available_version = await self._api.get_available_version(self._endpoint_id, self._container_name)
            self._state = available_version
        except Exception as e:
            _LOGGER.warning("Failed to get available version for %s: %s", self._attr_name, e)
            self._state = None

    @property
    def icon(self):
        return "mdi:update"