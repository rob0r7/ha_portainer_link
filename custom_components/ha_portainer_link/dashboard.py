from __future__ import annotations

import logging
from typing import Any, Dict, List

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

DASHBOARD_PATH_DEFAULT = "ha-protainer-link"
DASHBOARD_TITLE_DEFAULT = "HA Protainer Link"


async def ensure_dashboard_exists(hass: HomeAssistant, *, title: str = DASHBOARD_TITLE_DEFAULT, url_path: str = DASHBOARD_PATH_DEFAULT) -> None:
    """Ensure a storage-based Lovelace dashboard exists with the desired views.

    This uses the Lovelace storage collection to create/update a dashboard and set its config.
    The dashboard will contain:
      - A Home view with overview and global update count
      - A Controls view with all container and stack control buttons
      - A Containers view listing per-container: switch, Restart, Pull Update, Status, Update Available
      - A Stacks view (if stack entities exist) with stack buttons
    Only the Status sensor and Update Available binary_sensor are included from sensors as requested.
    """
    # Build entity lists from registry/state machine
    container_switches: List[str] = []
    container_restart_buttons: List[str] = []
    container_pull_buttons: List[str] = []
    container_status_sensors: List[str] = []
    container_update_bin: List[str] = []

    stack_start_buttons: List[str] = []
    stack_stop_buttons: List[str] = []
    stack_update_buttons: List[str] = []

    for state_obj in hass.states.async_all():
        entity_id = state_obj.entity_id
        domain = entity_id.split(".", 1)[0]
        name = state_obj.name or ""
        if domain == "switch" and name.endswith(" Switch"):
            container_switches.append(entity_id)
        elif domain == "button" and name.endswith(" Restart"):
            container_restart_buttons.append(entity_id)
        elif domain == "button" and name.endswith(" Pull Update"):
            container_pull_buttons.append(entity_id)
        elif domain == "sensor" and name.endswith(" Status"):
            container_status_sensors.append(entity_id)
        elif domain == "binary_sensor" and name.endswith(" Update Available"):
            container_update_bin.append(entity_id)
        elif domain == "button" and name.startswith("Stack: ") and name.endswith(" Start"):
            stack_start_buttons.append(entity_id)
        elif domain == "button" and name.startswith("Stack: ") and name.endswith(" Stop"):
            stack_stop_buttons.append(entity_id)
        elif domain == "button" and name.startswith("Stack: ") and name.endswith(" Update"):
            stack_update_buttons.append(entity_id)

    # Sort for stable layout
    container_switches.sort()
    container_restart_buttons.sort()
    container_pull_buttons.sort()
    container_status_sensors.sort()
    container_update_bin.sort()

    stack_start_buttons.sort()
    stack_stop_buttons.sort()
    stack_update_buttons.sort()

    # Global update count sensor via template (inline in card via jinja is not supported),
    # so we will build a simple entities card grouping update binaries.
    overview_cards: List[Dict[str, Any]] = []
    if container_update_bin:
        overview_cards.append({
            "type": "entity",
            "entity": container_update_bin[0],
            "name": "Example: Update Available",
            "icon": "mdi:update",
        })
        # Also show a glance of all update flags
        overview_cards.append({
            "type": "glance",
            "title": "Container Updates",
            "entities": container_update_bin[:30],
            "show_name": True,
            "show_icon": True,
        })

    # Controls view combines switches and buttons
    controls_cards: List[Dict[str, Any]] = []
    if container_switches:
        controls_cards.append({
            "type": "entities",
            "title": "Container Switches",
            "entities": container_switches,
            "state_color": True,
        })
    if container_restart_buttons:
        controls_cards.append({
            "type": "entities",
            "title": "Restart Buttons",
            "entities": container_restart_buttons,
        })
    if container_pull_buttons:
        controls_cards.append({
            "type": "entities",
            "title": "Pull Update Buttons",
            "entities": container_pull_buttons,
        })

    # Containers view: per-container rows combining controls + status + update
    # For simplicity, show grouped entities lists
    container_cards: List[Dict[str, Any]] = []
    if container_status_sensors:
        container_cards.append({
            "type": "entities",
            "title": "Container Status",
            "entities": container_status_sensors,
        })
    if container_update_bin:
        container_cards.append({
            "type": "entities",
            "title": "Update Available",
            "entities": container_update_bin,
        })

    # Stacks view
    stacks_cards: List[Dict[str, Any]] = []
    stack_entities: List[str] = []
    stack_entities.extend(stack_start_buttons)
    stack_entities.extend(stack_stop_buttons)
    stack_entities.extend(stack_update_buttons)
    if stack_entities:
        stacks_cards.append({
            "type": "entities",
            "title": "Stack Controls",
            "entities": stack_entities,
        })

    # Build views
    views: List[Dict[str, Any]] = []
    views.append({
        "title": "Home",
        "path": "home",
        "cards": overview_cards or [{"type": "markdown", "content": "No Portainer entities found yet."}],
        "theme": "",
        "badges": [],
    })

    if controls_cards:
        views.append({
            "title": "Controls",
            "path": "controls",
            "cards": controls_cards,
        })

    if container_cards:
        views.append({
            "title": "Containers",
            "path": "containers",
            "cards": container_cards,
        })

    if stacks_cards:
        views.append({
            "title": "Stacks",
            "path": "stacks",
            "cards": stacks_cards,
        })

    # Compose full dashboard config
    ll_config: Dict[str, Any] = {
        "title": title,
        "views": views,
    }

    # Create or update the dashboard in storage
    try:
        from homeassistant.components.lovelace import dashboards as ll_dash
        store = ll_dash.LovelaceDashboards(hass)

        # If exists, update; otherwise create
        existing = await store.async_get_dashboard(url_path)
        if existing is None:
            await store.async_create_dashboard(url_path=url_path, title=title, mode="storage", require_admin=False, show_in_sidebar=True, icon="mdi:docker")
            _LOGGER.info("Created dashboard '%s' at path '%s'", title, url_path)
        else:
            # Update title/visibility if changed
            if existing.get("title") != title or not existing.get("show_in_sidebar", True):
                await store.async_update_dashboard(url_path=url_path, title=title, show_in_sidebar=True, icon=existing.get("icon") or "mdi:docker")
                _LOGGER.info("Updated dashboard meta for path '%s'", url_path)

        # Now set dashboard content configuration
        await store.async_save_config(url_path=url_path, config=ll_config)
        _LOGGER.info("Saved dashboard config for '%s'", url_path)
    except Exception as e:  # noqa: BLE001
        _LOGGER.warning("Failed to create/update Lovelace dashboard: %s", e)