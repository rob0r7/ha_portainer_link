"""Button platform for HA Portainer Link."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity

from .const import CONF_NOTIFY_SERVICE, DATA_COORDINATOR, DOMAIN
from .entity import BaseContainerEntity, BaseStackEntity, container_name


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up Portainer buttons."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    entities: list[ButtonEntity] = []

    if coordinator.is_container_buttons_enabled():
        for container_id, container in coordinator.containers.items():
            name = container_name(container)
            stack_info = coordinator.get_container_stack_info(container_id) or {}
            entities.extend(
                [
                    RestartContainerButton(coordinator, entry.entry_id, container_id, name, stack_info),
                    PullUpdateButton(coordinator, entry.entry_id, container_id, name, stack_info),
                ]
            )

    if coordinator.is_stack_view_enabled() and coordinator.is_stack_buttons_enabled():
        for stack_name in coordinator.stack_names():
            entities.extend(
                [
                    StackStartButton(coordinator, entry.entry_id, stack_name),
                    StackStopButton(coordinator, entry.entry_id, stack_name),
                    StackUpdateButton(coordinator, entry.entry_id, stack_name),
                ]
            )

    async_add_entities(entities)


async def _send_notification(hass, coordinator, title: str, message: str) -> None:
    """Send a notification without assuming a mobile_app notify target exists."""
    notify_service = (coordinator.config.get(CONF_NOTIFY_SERVICE) or "").strip()
    if notify_service and "." in notify_service:
        domain, service = notify_service.split(".", 1)
        await hass.services.async_call(domain, service, {"title": title, "message": message}, blocking=False)
        return
    await hass.services.async_call(
        "persistent_notification",
        "create",
        {"title": title, "message": message},
        blocking=False,
    )


class ContainerButton(BaseContainerEntity, ButtonEntity):
    """Base class for container buttons."""

    def __init__(self, coordinator, entry_id, container_id, name, stack_info) -> None:
        super().__init__(coordinator, entry_id, container_id, name, stack_info)
        self._attr_name = f"{name} {self.label}"

    async def _notify(self, title: str, message: str) -> None:
        await _send_notification(self.hass, self.coordinator, title, message)


class RestartContainerButton(ContainerButton):
    """Restart a Docker container."""

    entity_suffix = "restart"
    label = "Restart"
    _attr_icon = "mdi:restart"

    async def async_press(self) -> None:
        container_id = self.current_container_id
        if not container_id:
            return
        success = await self.coordinator.api.restart_container(self.endpoint_id, container_id)
        await self.coordinator.async_request_refresh()
        if not success:
            await self._notify("Container Restart Failed", f"Failed to restart {self.container_name}")


class PullUpdateButton(ContainerButton):
    """Pull the latest image for a Docker container."""

    entity_suffix = "pull_update"
    label = "Pull Update"
    _attr_icon = "mdi:download"

    async def async_press(self) -> None:
        container_id = self.current_container_id
        if not container_id:
            return
        self._attr_available = False
        self.async_write_ha_state()
        try:
            success = await self.coordinator.api.pull_image_update(self.endpoint_id, container_id)
            await self.coordinator.async_request_refresh()
            if success:
                await self._notify("Container Image Pulled", f"Pulled latest image for {self.container_name}")
            else:
                await self._notify("Container Image Pull Failed", f"Failed to pull image for {self.container_name}")
        finally:
            self._attr_available = True
            self.async_write_ha_state()


class StackButton(BaseStackEntity, ButtonEntity):
    """Base class for stack buttons."""

    def __init__(self, coordinator, entry_id, stack_name) -> None:
        super().__init__(coordinator, entry_id, stack_name)
        self._attr_name = f"Stack: {stack_name} {self.label}"

    async def _notify(self, title: str, message: str) -> None:
        await _send_notification(self.hass, self.coordinator, title, message)


class StackStartButton(StackButton):
    """Start all containers in a stack."""

    entity_suffix = "start"
    label = "Start"
    _attr_icon = "mdi:play-circle"

    async def async_press(self) -> None:
        success = await self.coordinator.api.start_stack(self.endpoint_id, self.stack_name)
        await self.coordinator.async_request_refresh()
        if not success:
            await self._notify("Stack Start Failed", f"Failed to start stack {self.stack_name}")


class StackStopButton(StackButton):
    """Stop all containers in a stack."""

    entity_suffix = "stop"
    label = "Stop"
    _attr_icon = "mdi:stop-circle"

    async def async_press(self) -> None:
        success = await self.coordinator.api.stop_stack(self.endpoint_id, self.stack_name)
        await self.coordinator.async_request_refresh()
        if not success:
            await self._notify("Stack Stop Failed", f"Failed to stop stack {self.stack_name}")


class StackUpdateButton(StackButton):
    """Update a Portainer stack."""

    entity_suffix = "update"
    label = "Update"
    _attr_icon = "mdi:update"

    async def async_press(self) -> None:
        result = await self.coordinator.api.update_stack(self.endpoint_id, self.stack_name)
        await self.coordinator.async_request_refresh()
        if isinstance(result, dict):
            success = bool(result.get("ok", False))
        else:
            success = bool(result)
        if success:
            await self._notify("Stack Updated", f"Updated stack {self.stack_name}")
        else:
            await self._notify("Stack Update Failed", f"Failed to update stack {self.stack_name}")
