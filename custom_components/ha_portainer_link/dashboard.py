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
    _LOGGER.info("🔄 Starting dashboard creation/update for '%s' at path '%s'", title, url_path)
    
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

    # Create dashboard by writing storage files directly - much simpler and more reliable!
    _LOGGER.info("Creating dashboard by writing storage files directly...")
    
    try:
        import json
        from pathlib import Path
        
        # Get Home Assistant config directory
        config_dir = Path(hass.config.config_dir)
        storage_dir = config_dir / ".storage"
        
        # Dashboard metadata file (lovelace_dashboards.json)
        dashboards_file = storage_dir / "lovelace_dashboards.json"
        
        # NEVER create lovelace as a directory - Home Assistant uses it as a JSON file!
        # Clean up any incorrectly created directory FIRST, before any other operations
        lovelace_path = storage_dir / "lovelace"
        
        def _cleanup_lovelace_directory():
            if lovelace_path.exists() and lovelace_path.is_dir():
                _LOGGER.warning("⚠️ Removing incorrectly created lovelace directory - Home Assistant expects this to be a JSON file, not a directory!")
                import shutil
                try:
                    shutil.rmtree(lovelace_path)
                    _LOGGER.info("✅ Successfully removed lovelace directory")
                    return True
                except Exception as e:
                    _LOGGER.error("❌ Failed to remove lovelace directory: %s", e)
                    return False
            return True
        
        cleanup_success = await hass.async_add_executor_job(_cleanup_lovelace_directory)
        if not cleanup_success:
            _LOGGER.error("Could not clean up lovelace directory - dashboard creation may fail")
        
        # Store dashboard config in a safe location that won't conflict with Home Assistant files
        # Use our own directory that won't interfere
        config_file = storage_dir / "lovelace_dashboards_config" / f"{url_path}.json"
        
        # Read existing dashboards using async executor
        def _read_dashboards():
            if dashboards_file.exists():
                try:
                    with open(dashboards_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as e:
                    _LOGGER.warning("Could not read existing dashboards file: %s", e)
            return {}
        
        dashboards_data = await hass.async_add_executor_job(_read_dashboards)
        
        # Ensure proper structure
        if "data" not in dashboards_data:
            dashboards_data = {"data": {"items": []}}
        if "items" not in dashboards_data["data"]:
            dashboards_data["data"]["items"] = []
        
        # Check if dashboard already exists
        existing_dashboard = None
        for item in dashboards_data["data"]["items"]:
            if item.get("url_path") == url_path:
                existing_dashboard = item
                break
        
        # Create or update dashboard metadata
        dashboard_meta = {
            "url_path": url_path,
            "title": title,
            "icon": "mdi:docker",
            "require_admin": False,
            "show_in_sidebar": True,
            "mode": "storage"
        }
        
        if existing_dashboard:
            # Update existing
            existing_dashboard.update(dashboard_meta)
            _LOGGER.info("Updated dashboard metadata for '%s'", url_path)
        else:
            # Add new dashboard
            dashboards_data["data"]["items"].append(dashboard_meta)
            _LOGGER.info("Added dashboard metadata for '%s'", url_path)
        
        # Write dashboard metadata file using async executor
        def _write_dashboards():
            storage_dir.mkdir(exist_ok=True)
            with open(dashboards_file, 'w', encoding='utf-8') as f:
                json.dump(dashboards_data, f, indent=2, ensure_ascii=False)
        
        await hass.async_add_executor_job(_write_dashboards)
        _LOGGER.info("✅ Saved dashboard metadata to: %s", dashboards_file)
        
        # Write dashboard config file using async executor
        def _write_config():
            # Create parent directory safely - this is our dedicated directory, not lovelace
            config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(ll_config, f, indent=2, ensure_ascii=False)
        
        await hass.async_add_executor_job(_write_config)
        _LOGGER.info("✅ Saved dashboard config to: %s", config_file)
        _LOGGER.info("✅ Successfully created dashboard '%s' at /%s", title, url_path)
        
        # Try to reload Lovelace to pick up the new dashboard
        try:
            await hass.services.async_call("lovelace", "reload", {}, blocking=False)
            _LOGGER.info("Triggered Lovelace reload")
        except Exception:
            _LOGGER.debug("Could not trigger Lovelace reload service")
        
    except Exception as e:
        _LOGGER.error("❌ Failed to create dashboard files: %s", e, exc_info=True)
