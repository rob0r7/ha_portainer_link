from __future__ import annotations

import logging
from typing import Any, Dict, List

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, device_registry as dr

_LOGGER = logging.getLogger(__name__)

DASHBOARD_PATH_DEFAULT = "ha-portainer-link"
DASHBOARD_TITLE_DEFAULT = "HA Portainer Link"


async def ensure_dashboard_exists(hass: HomeAssistant, *, title: str = DASHBOARD_TITLE_DEFAULT, url_path: str = DASHBOARD_PATH_DEFAULT) -> None:
    """Ensure a storage-based Lovelace dashboard exists with the desired views.

    This uses the Lovelace storage collection to create/update a dashboard and set its config.
    The dashboard will contain:
      - A Home view with overview and global update count
      - One view per stack (plus a Standalone view) with controls and the two requested sensors
    Only the Status sensor and Update Available binary_sensor are included from sensors as requested.
    """
    # Build entity lists grouped by stack device
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    def _group_name_for(state_obj) -> str:
        entry = ent_reg.async_get(state_obj.entity_id)
        if not entry or not entry.device_id:
            return "Standalone"
        device = dev_reg.async_get(entry.device_id)
        if not device:
            return "Standalone"
        # Stack devices are created by this integration with model "Docker Stack" and name "Stack: {stack} ({host})"
        name = device.name or ""
        model = device.model or ""
        if model == "Docker Stack" or name.startswith("Stack: "):
            # Extract stack name from device name when possible
            if name.startswith("Stack: ") and " (" in name:
                return name[len("Stack: "): name.find(" (")]
            return name or "Stack"
        return "Standalone"

    groups: Dict[str, Dict[str, List[str]]] = {}
    def gkey(stack: str) -> Dict[str, List[str]]:
        return groups.setdefault(stack, {
            "switches": [],
            "restart_buttons": [],
            "pull_buttons": [],
            "status_sensors": [],
            "update_bin": [],
            "stack_buttons": [],
        })

    for state_obj in hass.states.async_all():
        eid = state_obj.entity_id
        domain = eid.split(".", 1)[0]
        name = state_obj.name or ""
        grp = _group_name_for(state_obj)
        bucket = gkey(grp)
        if domain == "switch" and name.endswith(" Switch"):
            bucket["switches"].append(eid)
        elif domain == "button" and name.startswith("Stack: "):
            bucket["stack_buttons"].append(eid)
        elif domain == "button" and name.endswith(" Restart"):
            bucket["restart_buttons"].append(eid)
        elif domain == "button" and name.endswith(" Pull Update"):
            bucket["pull_buttons"].append(eid)
        elif domain == "sensor" and name.endswith(" Status"):
            bucket["status_sensors"].append(eid)
        elif domain == "binary_sensor" and name.endswith(" Update Available"):
            bucket["update_bin"].append(eid)

    # Sort entities for stable layouts
    for bucket in groups.values():
        for key in bucket:
            bucket[key].sort()

    # Home view (overview)
    all_updates = [eid for b in groups.values() for eid in b["update_bin"]]
    overview_cards: List[Dict[str, Any]] = []
    if all_updates:
        overview_cards.append({
            "type": "glance",
            "title": "Container Updates",
            "entities": all_updates[:30],
            "show_name": True,
            "show_icon": True,
        })
    else:
        overview_cards.append({"type": "markdown", "content": "No Portainer entities found yet."})

    # Build one view per stack plus a Standalone view
    def _slugify(text: str) -> str:
        return text.lower().replace(" ", "-").replace("/", "-")

    views: List[Dict[str, Any]] = []
    views.append({
        "title": "Home",
        "path": "home",
        "cards": overview_cards,
        "badges": [],
    })

    for stack_name in sorted([k for k in groups.keys() if k != "Standalone"], key=lambda s: s.lower()):
        b = groups[stack_name]
        cards: List[Dict[str, Any]] = []
        if b["stack_buttons"]:
            cards.append({
                "type": "entities",
                "title": "Stack Controls",
                "entities": b["stack_buttons"],
            })
        if b["switches"]:
            cards.append({
                "type": "entities",
                "title": "Container Switches",
                "entities": b["switches"],
                "state_color": True,
            })
        if b["restart_buttons"]:
            cards.append({
                "type": "entities",
                "title": "Restart Buttons",
                "entities": b["restart_buttons"],
            })
        if b["pull_buttons"]:
            cards.append({
                "type": "entities",
                "title": "Pull Update Buttons",
                "entities": b["pull_buttons"],
            })
        if b["status_sensors"]:
            cards.append({
                "type": "entities",
                "title": "Status",
                "entities": b["status_sensors"],
            })
        if b["update_bin"]:
            cards.append({
                "type": "entities",
                "title": "Update Available",
                "entities": b["update_bin"],
            })
        if cards:
            views.append({
                "title": f"Stack: {stack_name}",
                "path": _slugify(stack_name),
                "cards": cards,
            })

    # Standalone view last
    if "Standalone" in groups:
        b = groups["Standalone"]
        cards: List[Dict[str, Any]] = []
        if b["switches"]:
            cards.append({
                "type": "entities",
                "title": "Container Switches",
                "entities": b["switches"],
                "state_color": True,
            })
        if b["restart_buttons"]:
            cards.append({
                "type": "entities",
                "title": "Restart Buttons",
                "entities": b["restart_buttons"],
            })
        if b["pull_buttons"]:
            cards.append({
                "type": "entities",
                "title": "Pull Update Buttons",
                "entities": b["pull_buttons"],
            })
        if b["status_sensors"]:
            cards.append({
                "type": "entities",
                "title": "Status",
                "entities": b["status_sensors"],
            })
        if b["update_bin"]:
            cards.append({
                "type": "entities",
                "title": "Update Available",
                "entities": b["update_bin"],
            })
        if cards:
            views.append({
                "title": "Standalone",
                "path": "standalone",
                "cards": cards,
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

        # Compatibility for method names across HA versions
        get_method = getattr(store, "async_get", None) or getattr(store, "async_get_dashboard")
        create_method = getattr(store, "async_create", None) or getattr(store, "async_create_dashboard")
        update_method = getattr(store, "async_update", None) or getattr(store, "async_update_dashboard")

        existing = await get_method(url_path)
        if existing is None:
            # Some HA versions do not accept a 'mode' parameter here
            await create_method(
                url_path=url_path,
                title=title,
                require_admin=False,
                show_in_sidebar=True,
                icon="mdi:docker",
            )
            _LOGGER.info("Created dashboard '%s' at path '%s'", title, url_path)
        else:
            # Keep metadata in sync
            if existing.get("title") != title or not existing.get("show_in_sidebar", True):
                await update_method(
                    url_path=url_path,
                    title=title,
                    show_in_sidebar=True,
                    icon=existing.get("icon") or "mdi:docker",
                )
                _LOGGER.info("Updated dashboard meta for path '%s'", url_path)

        # Save the config using the method available in this HA version
        if hasattr(store, "async_save_config"):
            await store.async_save_config(url_path=url_path, config=ll_config)
        elif hasattr(store, "async_save"):
            # Older/newer core versions use a shorter name
            await store.async_save(url_path=url_path, config=ll_config)
        else:
            raise AttributeError("No supported save method found for LovelaceDashboards")

        _LOGGER.info("Saved dashboard config for '%s'", url_path)
    except Exception as e:  # noqa: BLE001
        _LOGGER.exception("Failed to create/update Lovelace dashboard: %s", e)