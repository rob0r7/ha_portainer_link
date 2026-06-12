"""Data coordinator for HA Portainer Link."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import time
from typing import Any

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
)
from .entity import container_name, is_container_running, stable_container_key, stack_info_from_container
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
        self.containers: dict[str, dict[str, Any]] = {}
        self.stacks: dict[str, dict[str, Any]] = {}
        self.container_stack_map: dict[str, str] = {}
        self.container_stack_info: dict[str, dict[str, Any]] = {}
        self.stable_container_map: dict[str, str] = {}
        self.metrics: dict[str, dict[str, Any]] = {}
        self.image_data: dict[str, dict[str, Any]] = {}
        self.update_availability: dict[str, bool] = {}
        self._last_registry_check = 0.0
        self.last_success: dt.datetime | None = None
        self.last_registry_check: dt.datetime | None = None
        self.last_update_reasons: dict[str, str] = {}

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

            if self.is_resource_sensors_enabled():
                await self._refresh_metrics()
            else:
                self.metrics = {}

            await self._refresh_image_data_if_due()
            self.last_success = dt.datetime.now(dt.timezone.utc)
            self.api.clear_error()

            return {
                "containers": self.containers,
                "stacks": self.stacks,
                "container_stack_map": self.container_stack_map,
                "metrics": self.metrics,
                "image_data": self.image_data,
                "update_availability": self.update_availability,
            }
        except Exception as err:
            self.api.record_error(err)
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

    async def _refresh_metrics(self) -> None:
        """Refresh resource metrics with bounded concurrency."""
        metrics: dict[str, dict[str, Any]] = {}
        semaphore = asyncio.Semaphore(4)

        async def refresh_one(container_id: str, container: dict[str, Any]) -> None:
            async with semaphore:
                item: dict[str, Any] = {}
                if is_container_running(container):
                    stats = await self.api.get_container_stats(self.endpoint_id, container_id)
                    item.update(self._parse_stats(stats or {}))
                    started_at = await self._get_started_at(container_id)
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

        cpu_usage = cpu_stats.get("cpu_usage") or {}
        precpu_usage = precpu_stats.get("cpu_usage") or {}
        cpu_total = cpu_usage.get("total_usage") or cpu_usage.get("total") or 0
        precpu_total = precpu_usage.get("total_usage") or precpu_usage.get("total") or 0
        system_total = cpu_stats.get("system_cpu_usage") or cpu_stats.get("system_usage") or 0
        pre_system_total = precpu_stats.get("system_cpu_usage") or precpu_stats.get("system_usage") or 0
        system_delta = max(0, system_total - pre_system_total)
        cpu_delta = max(0, cpu_total - precpu_total)
        if system_delta > 0 and cpu_delta >= 0:
            online_cpus = (
                cpu_stats.get("online_cpus")
                or len(cpu_usage.get("percpu_usage") or [])
                or 1
            )
            parsed["cpu_percent"] = round((cpu_delta / system_delta) * online_cpus * 100.0, 2)

        memory_stats = stats.get("memory_stats") or {}
        memory_usage = memory_stats.get("usage")
        if memory_usage is not None:
            parsed["memory_mb"] = round(memory_usage / (1024 * 1024), 2)
            memory_detail = memory_stats.get("stats") or {}
            cache = memory_detail.get("inactive_file") or memory_detail.get("cache") or 0
            if cache and memory_usage:
                parsed["memory_effective_mb"] = round(max(0, memory_usage - cache) / (1024 * 1024), 2)
        return parsed

    async def _get_started_at(self, container_id: str) -> dt.datetime | None:
        """Return StartedAt for a running container."""
        try:
            info = await self.api.inspect_container(self.endpoint_id, container_id)
            started_at = ((info or {}).get("State") or {}).get("StartedAt")
            if not started_at or started_at.startswith("0001-"):
                return None
            parsed = dt.datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
        except Exception as err:
            _LOGGER.debug("Failed to parse uptime for %s: %s", container_id, err)
            return None

    async def _refresh_image_data_if_due(self) -> None:
        """Refresh image metadata and optional registry data."""
        if not (self.is_version_sensors_enabled() or self.is_update_sensors_enabled()):
            self.image_data = {}
            self.update_availability = {}
            return

        now = time.monotonic()
        interval = int(self.config.get(CONF_UPDATE_CHECK_INTERVAL, DEFAULT_OPTIONS[CONF_UPDATE_CHECK_INTERVAL]))
        registry_data_enabled = self.is_version_sensors_enabled() or self.is_update_sensors_enabled()
        include_registry = registry_data_enabled and (now - self._last_registry_check >= max(interval, 60))
        if include_registry:
            self._last_registry_check = now
            self.last_registry_check = dt.datetime.now(dt.timezone.utc)

        image_data: dict[str, dict[str, Any]] = {}
        update_availability = dict(self.update_availability)
        update_reasons = dict(self.last_update_reasons)
        semaphore = asyncio.Semaphore(3)

        async def refresh_one(container_id: str) -> None:
            async with semaphore:
                data: dict[str, Any] = {}
                reason = "disabled" if not self.is_update_sensors_enabled() else "remote_digest_unknown"
                try:
                    info = await self.api.inspect_container(self.endpoint_id, container_id)
                    image_name = ((info or {}).get("Config") or {}).get("Image")
                    image_id = (info or {}).get("Image")
                    if image_name:
                        data["image_name"] = image_name
                    if image_id:
                        image_info = await self.api.get_image_info(self.endpoint_id, image_id)
                        if image_info:
                            data["current_version"] = self.api.extract_version_from_image(image_info)
                        current_digest = await self.api.get_current_digest(self.endpoint_id, container_id)
                        if current_digest:
                            data["current_digest"] = current_digest
                        if include_registry and image_name:
                            data["last_checked"] = dt.datetime.now(dt.timezone.utc).isoformat()
                            data["detection_method"] = "digest"
                            available_digest = await self.api.get_available_digest(self.endpoint_id, container_id)
                            if available_digest and not str(available_digest).startswith("unknown"):
                                data["available_digest"] = available_digest
                            current_digest = data.get("current_digest")
                            has_update = bool(
                                current_digest
                                and not str(current_digest).startswith("unknown")
                                and available_digest
                                and not str(available_digest).startswith("unknown")
                                and current_digest != available_digest
                            )
                            update_availability[container_id] = has_update
                            if not current_digest or str(current_digest).startswith("unknown"):
                                reason = "local_digest_unknown"
                            elif not available_digest or str(available_digest).startswith("unknown"):
                                reason = "remote_digest_unknown"
                            elif has_update:
                                reason = "digest_changed"
                            else:
                                reason = "digest_matches"
                            data["update_reason"] = reason
                            update_reasons[container_id] = reason
                            data["available_version"] = await self.api.get_available_version(self.endpoint_id, image_name)
                except Exception as err:
                    _LOGGER.debug("Failed refresh image data for %s: %s", container_id, err)
                    reason = "registry_unreachable" if include_registry else reason
                    data["update_reason"] = reason
                    update_reasons[container_id] = reason
                image_data[container_id] = {**self.image_data.get(container_id, {}), **data}

        await asyncio.gather(*(refresh_one(container_id) for container_id in self.containers))
        self.image_data = image_data
        if include_registry and self.is_update_sensors_enabled():
            self.update_availability = {
                container_id: bool(update_availability.get(container_id, False))
                for container_id in self.containers
            }
            self.last_update_reasons = {
                container_id: update_reasons.get(container_id, "remote_digest_unknown")
                for container_id in self.containers
            }
        elif not self.is_update_sensors_enabled():
            self.update_availability = {}
            self.last_update_reasons = {}

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
