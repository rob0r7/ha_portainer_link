"""Data coordinator for HA Portainer Link."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import time
from typing import Any

from aiohttp.client_exceptions import ClientConnectorCertificateError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_ENABLE_CONTAINER_BUTTONS,
    CONF_ENABLE_RESOURCE_SENSORS,
    CONF_ENABLE_STACK_BUTTONS,
    CONF_ENABLE_STACK_VIEW,
    CONF_ENABLE_UPDATE_SENSORS,
    CONF_ENABLE_VERSION_SENSORS,
    CONF_UPDATE_CHECK_INTERVAL,
    CONF_UPDATE_INTERVAL,
    DEFAULT_OPTIONS,
    SSL_VERIFY_FAILED_MESSAGE,
)
from .entity import (
    container_name,
    is_container_running,
    is_portainer_image,
    stable_container_key,
    stack_info_from_container,
)
from .portainer_api import PortainerAPI

_LOGGER = logging.getLogger(__name__)


class PortainerDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator for Portainer container, stack, metric, and image data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: PortainerAPI,
        endpoint_id: int,
        config: dict[str, Any],
    ) -> None:
        self.config = {**DEFAULT_OPTIONS, **config}
        update_interval = int(self.config.get(CONF_UPDATE_INTERVAL, DEFAULT_OPTIONS[CONF_UPDATE_INTERVAL]))
        super().__init__(
            hass,
            _LOGGER,
            name=f"ha_portainer_link_{endpoint_id}",
            update_interval=dt.timedelta(minutes=max(update_interval, 1)),
        )
        self.api = api
        self.endpoint_id = endpoint_id
        if api.images:
            # Expire remote digests just before the next due check so the configured interval is honoured.
            check_interval = int(self.config.get(CONF_UPDATE_CHECK_INTERVAL, DEFAULT_OPTIONS[CONF_UPDATE_CHECK_INTERVAL]))
            api.images.set_cache_duration((max(check_interval, 60) - 1) * 60)
        self.containers: dict[str, dict[str, Any]] = {}
        self.stacks: dict[str, dict[str, Any]] = {}
        self.container_stack_map: dict[str, str] = {}
        self.container_stack_info: dict[str, dict[str, Any]] = {}
        self.stable_container_map: dict[str, str] = {}
        self.metrics: dict[str, dict[str, Any]] = {}
        self.image_data: dict[str, dict[str, Any]] = {}
        self.update_availability: dict[str, bool] = {}
        self._image_info_cache: dict[str, dict[str, Any]] = {}
        self._last_registry_check = 0.0

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch fresh data from Portainer."""
        try:
            if self.api.containers:
                endpoint_exists = await self.api.containers.check_endpoint_exists(self.endpoint_id)
                if not endpoint_exists:
                    raise UpdateFailed(f"Endpoint {self.endpoint_id} does not exist")

            containers = await self.api.get_containers(self.endpoint_id)
            stacks = await self.api.get_stacks(self.endpoint_id)
            self._process_containers(containers or [])
            self.stacks = {stack.get("Name"): stack for stack in (stacks or []) if stack.get("Name")}

            inspect_data = await self._inspect_containers()

            if self.is_resource_sensors_enabled():
                await self._refresh_metrics(inspect_data)
            else:
                self.metrics = {}

            await self._refresh_image_data_if_due(inspect_data)

            return {
                "containers": self.containers,
                "stacks": self.stacks,
                "container_stack_map": self.container_stack_map,
                "metrics": self.metrics,
                "image_data": self.image_data,
                "update_availability": self.update_availability,
            }
        except ClientConnectorCertificateError as err:
            raise UpdateFailed(SSL_VERIFY_FAILED_MESSAGE) from err
        except Exception as err:
            raise UpdateFailed(f"Failed to update Portainer data: {err}") from err

    def _process_containers(self, containers: list[dict[str, Any]]) -> None:
        """Normalize container list data into lookup maps."""
        self.containers = {}
        self.container_stack_map = {}
        self.container_stack_info = {}
        self.stable_container_map = {}

        for container in containers:
            container_id = container.get("Id")
            if not container_id:
                continue
            name = container_name(container)
            stack_info = stack_info_from_container(container)
            if not self.is_stack_view_enabled():
                stack_info = {
                    "stack_name": None,
                    "service_name": None,
                    "container_number": None,
                    "is_stack_container": False,
                }

            self.containers[container_id] = container
            self.container_stack_info[container_id] = stack_info
            if stack_info.get("is_stack_container"):
                self.container_stack_map[container_id] = stack_info["stack_name"]
            self.stable_container_map[stable_container_key(name, stack_info)] = container_id

    async def _inspect_containers(self) -> dict[str, dict[str, Any]]:
        """Inspect each needed container once per refresh; shared by metrics and image data."""
        need_image_data = self.is_version_sensors_enabled() or self.is_update_sensors_enabled()
        need_metrics = self.is_resource_sensors_enabled()
        if not (need_image_data or need_metrics):
            return {}

        targets = [
            container_id
            for container_id, container in self.containers.items()
            if need_image_data or is_container_running(container)
        ]
        results: dict[str, dict[str, Any]] = {}
        semaphore = asyncio.Semaphore(4)

        async def inspect_one(container_id: str) -> None:
            async with semaphore:
                try:
                    info = await self.api.inspect_container(self.endpoint_id, container_id)
                except Exception as err:
                    _LOGGER.debug("Failed to inspect container %s: %s", container_id, err)
                    return
                if info:
                    results[container_id] = info

        await asyncio.gather(*(inspect_one(container_id) for container_id in targets))
        return results

    async def _refresh_metrics(self, inspect_data: dict[str, dict[str, Any]]) -> None:
        """Refresh resource metrics with bounded concurrency."""
        metrics: dict[str, dict[str, Any]] = {}
        semaphore = asyncio.Semaphore(4)

        async def refresh_one(container_id: str, container: dict[str, Any]) -> None:
            async with semaphore:
                item: dict[str, Any] = {}
                if is_container_running(container):
                    stats = await self.api.get_container_stats(self.endpoint_id, container_id)
                    item.update(self._parse_stats(stats or {}))
                    started_at = self._parse_started_at(inspect_data.get(container_id))
                    if started_at:
                        item["uptime_s"] = max(0, int((dt.datetime.now(dt.timezone.utc) - started_at).total_seconds()))
                else:
                    item["uptime_s"] = None
                metrics[container_id] = item

        await asyncio.gather(*(refresh_one(cid, container) for cid, container in self.containers.items()))
        self.metrics = metrics

    @staticmethod
    def _parse_stats(stats: dict[str, Any]) -> dict[str, Any]:
        """Extract CPU and memory metrics from Docker stats."""
        parsed: dict[str, Any] = {}
        cpu_stats = stats.get("cpu_stats") or {}
        precpu_stats = stats.get("precpu_stats") or {}
        cpu_total = ((cpu_stats.get("cpu_usage") or {}).get("total_usage") or 0)
        precpu_total = ((precpu_stats.get("cpu_usage") or {}).get("total_usage") or 0)
        system_total = cpu_stats.get("system_cpu_usage") or 0
        pre_system_total = precpu_stats.get("system_cpu_usage") or 0
        system_delta = system_total - pre_system_total
        cpu_delta = cpu_total - precpu_total
        if system_delta > 0 and cpu_delta >= 0:
            online_cpus = cpu_stats.get("online_cpus") or 1
            parsed["cpu_percent"] = round((cpu_delta / system_delta) * online_cpus * 100.0, 2)

        memory_usage = (stats.get("memory_stats") or {}).get("usage")
        if memory_usage is not None:
            parsed["memory_mb"] = round(memory_usage / (1024 * 1024), 2)
        return parsed

    @staticmethod
    def _parse_started_at(info: dict[str, Any] | None) -> dt.datetime | None:
        """Return StartedAt from container inspect data."""
        try:
            started_at = ((info or {}).get("State") or {}).get("StartedAt")
            if not started_at or started_at.startswith("0001-"):
                return None
            parsed = dt.datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
        except Exception as err:
            _LOGGER.debug("Failed to parse container uptime: %s", err)
            return None

    async def _refresh_image_data_if_due(self, inspect_data: dict[str, dict[str, Any]]) -> None:
        """Refresh image metadata and optional registry data."""
        if not (self.is_version_sensors_enabled() or self.is_update_sensors_enabled()):
            self.image_data = {}
            self.update_availability = {}
            self._image_info_cache = {}
            return

        now = time.monotonic()
        interval = int(self.config.get(CONF_UPDATE_CHECK_INTERVAL, DEFAULT_OPTIONS[CONF_UPDATE_CHECK_INTERVAL]))
        include_registry = now - self._last_registry_check >= max(interval, 60)
        if include_registry:
            self._last_registry_check = now

        await self._refresh_image_info_cache(inspect_data, force=include_registry)

        image_data: dict[str, dict[str, Any]] = {}
        update_availability = dict(self.update_availability)
        semaphore = asyncio.Semaphore(3)

        async def refresh_one(container_id: str) -> None:
            async with semaphore:
                data: dict[str, Any] = {}
                try:
                    info = inspect_data.get(container_id) or {}
                    image_name = (info.get("Config") or {}).get("Image")
                    image_id = info.get("Image")
                    if image_name:
                        data["image_name"] = image_name
                    if image_info := self._image_info_cache.get(image_id or ""):
                        data["current_version"] = self.api.extract_version_from_image(image_info)
                        data["current_digest"] = self.api.images.get_local_digest(image_info, image_name)
                    if include_registry and image_name:
                        available_digest = await self.api.images.get_available_digest_for_image(
                            image_name, data.get("current_digest")
                        )
                        if available_digest and not str(available_digest).startswith("unknown"):
                            data["available_digest"] = available_digest
                            current_digest = data.get("current_digest")
                            update_availability[container_id] = bool(
                                current_digest
                                and not str(current_digest).startswith("unknown")
                                and current_digest != available_digest
                            )
                        data["available_version"] = await self.api.get_available_version(self.endpoint_id, image_name)
                except Exception as err:
                    _LOGGER.debug("Failed to refresh image data for %s: %s", container_id, err)
                image_data[container_id] = {**self.image_data.get(container_id, {}), **data}

        await asyncio.gather(*(refresh_one(container_id) for container_id in self.containers))
        self.image_data = image_data
        if include_registry and self.is_update_sensors_enabled():
            self.update_availability = {
                container_id: bool(update_availability.get(container_id, False))
                for container_id in self.containers
            }
        elif not self.is_update_sensors_enabled():
            self.update_availability = {}

    async def _refresh_image_info_cache(self, inspect_data: dict[str, dict[str, Any]], *, force: bool) -> None:
        """Fetch local image metadata once per image ID.

        Image IDs are content addressed, so cached entries are reused between polls and
        only re-fetched together with the registry check or when a new image ID appears.
        """
        image_ids = {info.get("Image") for info in inspect_data.values() if info.get("Image")}
        cache: dict[str, dict[str, Any]] = {}
        if not force:
            cache = {
                image_id: self._image_info_cache[image_id]
                for image_id in image_ids
                if image_id in self._image_info_cache
            }
        semaphore = asyncio.Semaphore(3)

        async def fetch_one(image_id: str) -> None:
            async with semaphore:
                try:
                    image_info = await self.api.get_image_info(self.endpoint_id, image_id)
                except Exception as err:
                    _LOGGER.debug("Failed to get image info for %s: %s", image_id, err)
                    return
                if image_info:
                    cache[image_id] = image_info

        await asyncio.gather(*(fetch_one(image_id) for image_id in image_ids if image_id not in cache))
        self._image_info_cache = cache

    def get_container(self, container_id: str | None) -> dict[str, Any] | None:
        return self.containers.get(container_id or "")

    def get_stack(self, stack_name: str) -> dict[str, Any] | None:
        return self.stacks.get(stack_name)

    def get_container_stack(self, container_id: str) -> str | None:
        return self.container_stack_map.get(container_id)

    def get_container_stack_info(self, container_id: str) -> dict[str, Any] | None:
        return self.container_stack_info.get(container_id)

    def get_update_availability(self, container_id: str | None) -> bool:
        return bool(self.update_availability.get(container_id or "", False))

    def is_portainer_container(self, container_id: str | None) -> bool:
        """Return whether a container runs Portainer or its agent; it must not be recreated via the API."""
        container = self.get_container(container_id) or {}
        image_name = self.image_data.get(container_id or "", {}).get("image_name") or container.get("Image")
        return is_portainer_image(image_name)

    def get_container_by_stable_id(self, stable_id: str) -> str | None:
        return self.stable_container_map.get(stable_id)

    def get_stack_containers(self, stack_name: str) -> list[dict[str, Any]]:
        return [
            container
            for container_id, container in self.containers.items()
            if self.container_stack_map.get(container_id) == stack_name
        ]

    def get_standalone_containers(self) -> list[dict[str, Any]]:
        return [
            container
            for container_id, container in self.containers.items()
            if container_id not in self.container_stack_map
        ]

    def stack_names(self) -> list[str]:
        names = set(self.stacks)
        names.update(name for name in self.container_stack_map.values() if name)
        return sorted(names)

    def is_stack_view_enabled(self) -> bool:
        return bool(self.config.get(CONF_ENABLE_STACK_VIEW))

    def is_resource_sensors_enabled(self) -> bool:
        return bool(self.config.get(CONF_ENABLE_RESOURCE_SENSORS))

    def is_version_sensors_enabled(self) -> bool:
        return bool(self.config.get(CONF_ENABLE_VERSION_SENSORS))

    def is_update_sensors_enabled(self) -> bool:
        return bool(self.config.get(CONF_ENABLE_UPDATE_SENSORS))

    def is_stack_buttons_enabled(self) -> bool:
        return bool(self.config.get(CONF_ENABLE_STACK_BUTTONS))

    def is_container_buttons_enabled(self) -> bool:
        return bool(self.config.get(CONF_ENABLE_CONTAINER_BUTTONS))

    async def async_shutdown(self) -> None:
        """Close API resources."""
        await self.api.close()
