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
        # Try multiple import paths for Lovelace dashboards to support newer/older HA versions
        store = None
        try:
            from homeassistant.components.lovelace import dashboards as ll_dash  # type: ignore
            store = ll_dash.LovelaceDashboards(hass)
        except Exception:  # noqa: BLE001
            try:
                from homeassistant.components.lovelace.dashboard import LovelaceDashboards as _LovelaceDashboards  # type: ignore[attr-defined]
                store = _LovelaceDashboards(hass)
            except Exception:  # noqa: BLE001
                try:
                    # Try newer HA versions with different import path
                    from homeassistant.components.lovelace.dashboard import LovelaceDashboards  # type: ignore
                    store = LovelaceDashboards(hass)
                except Exception:  # noqa: BLE001
                    try:
                                                 # Try to get from hass.data directly for newer versions
                         from homeassistant.components.lovelace import LovelaceManager  # type: ignore
                         potential_store = hass.data.get("lovelace")
                         # Validate that the potential store is not a basic type
                         if potential_store is not None and not isinstance(potential_store, (dict, list, str, int, float, bool)):
                             store = potential_store
                             _LOGGER.debug("Assigned store from hass.data.get('lovelace'): %s (type: %s)", store, type(store).__name__)
                         else:
                             _LOGGER.debug("Skipping hass.data.get('lovelace') - type: %s", type(potential_store).__name__ if potential_store is not None else "None")
                    except Exception:  # noqa: BLE001
                        store = None

        # Fallback: discover dashboards store from hass.data for newer HA versions
        if store is None:
            ll_data = hass.data.get("lovelace")
            _LOGGER.debug("Trying to find dashboard store in lovelace data: %s (type: %s)", ll_data, type(ll_data).__name__)
            
            if isinstance(ll_data, dict):
                # Older HA versions where lovelace data is a dict
                _LOGGER.debug("Lovelace data is a dict with keys: %s", list(ll_data.keys()))
                for _key, _val in ll_data.items():
                    # Only accept objects that have the essential dashboard methods and are not basic types
                    if (not isinstance(_val, (dict, list, str, int, float, bool)) and
                        hasattr(_val, "async_get") and 
                        hasattr(_val, "async_create") and 
                        hasattr(_val, "async_update")):
                        store = _val
                        _LOGGER.debug("Found store in dict key '%s': %s", _key, type(_val).__name__)
                        _LOGGER.debug("Assigned store from dict key '%s': %s (type: %s)", _key, store, type(store).__name__)
                        break
                    else:
                        _LOGGER.debug("Skipping dict key '%s' - type: %s, has methods: %s", 
                                     _key, type(_val).__name__,
                                     hasattr(_val, "async_get") and hasattr(_val, "async_create") and hasattr(_val, "async_update"))
            elif ll_data is not None:
                # Newer HA versions where lovelace data is a LovelaceData object
                # Try to get the dashboards store from the LovelaceData object
                try:
                    _LOGGER.debug("Lovelace data is a %s object", type(ll_data).__name__)
                    _LOGGER.debug("Available attributes: %s", [attr for attr in dir(ll_data) if not attr.startswith('_')])
                    
                    # Check if LovelaceData has a dashboards attribute
                    if hasattr(ll_data, "dashboards"):
                        potential_store = ll_data.dashboards
                        _LOGGER.debug("Found dashboards attribute: %s (type: %s)", potential_store, type(potential_store).__name__)
                        _LOGGER.debug("Dashboards object methods: %s", [attr for attr in dir(potential_store) if not attr.startswith('_') and callable(getattr(potential_store, attr, None))])
                        
                        # Check for various method name patterns that might exist
                        has_get = (hasattr(potential_store, "async_get") or 
                                  hasattr(potential_store, "async_get_dashboard") or
                                  hasattr(potential_store, "get") or
                                  hasattr(potential_store, "get_dashboard"))
                        has_create = (hasattr(potential_store, "async_create") or 
                                    hasattr(potential_store, "async_create_dashboard") or
                                    hasattr(potential_store, "create") or
                                    hasattr(potential_store, "create_dashboard"))
                        has_update = (hasattr(potential_store, "async_update") or 
                                    hasattr(potential_store, "async_update_dashboard") or
                                    hasattr(potential_store, "update") or
                                    hasattr(potential_store, "update_dashboard"))
                        
                        _LOGGER.debug("Method check results - get: %s, create: %s, update: %s", has_get, has_create, has_update)
                        
                        # For now, only require the essential methods (get, create, update)
                        # Save method might be handled differently in newer HA versions
                        if has_get and has_create and has_update:
                            # Validate that potential_store is not a basic type before using it
                            if not isinstance(potential_store, (dict, list, str, int, float, bool)):
                                store = potential_store
                                _LOGGER.debug("Found valid store in dashboards attribute: %s", type(store).__name__)
                                _LOGGER.debug("Assigned store from dashboards attribute: %s (type: %s)", store, type(store).__name__)
                            else:
                                _LOGGER.debug("Skipping dashboards attribute - it's a basic type: %s", type(potential_store).__name__)
                        else:
                            _LOGGER.debug("Dashboards object missing required methods - get: %s, create: %s, update: %s", 
                                         has_get, has_create, has_update)
                            
                            # Try to find any method that might be useful
                            for method_name in ['async_get', 'async_get_dashboard', 'get', 'get_dashboard', 
                                              'async_create', 'async_create_dashboard', 'create', 'create_dashboard',
                                              'async_update', 'async_update_dashboard', 'update', 'update_dashboard']:
                                if hasattr(potential_store, method_name):
                                    _LOGGER.debug("Found method '%s' on dashboards object", method_name)
                                    
                            # Even if we don't have all methods, try to use this as a store
                            # Some newer HA versions might handle missing methods differently
                            if has_get or has_create or has_update:
                                # Validate that potential_store is not a basic type before using it
                                if not isinstance(potential_store, (dict, list, str, int, float, bool)):
                                    _LOGGER.info("Attempting to use dashboards object with partial method support")
                                    store = potential_store
                                    _LOGGER.debug("Assigned store from dashboards attribute (partial support): %s (type: %s)", store, type(store).__name__)
                                else:
                                    _LOGGER.debug("Skipping dashboards attribute (partial support) - it's a basic type: %s", type(potential_store).__name__)
                    # Check if LovelaceData itself has the required methods
                    elif (hasattr(ll_data, "async_get") and 
                          hasattr(ll_data, "async_create") and
                          hasattr(ll_data, "async_update")):
                        # Validate that ll_data is not a basic type before using it
                        if not isinstance(ll_data, (dict, list, str, int, float, bool)):
                            store = ll_data
                            _LOGGER.debug("Found store in LovelaceData object itself")
                            _LOGGER.debug("Assigned store from LovelaceData object: %s (type: %s)", store, type(store).__name__)
                        else:
                            _LOGGER.debug("Skipping LovelaceData object itself - it's a basic type: %s", type(ll_data).__name__)
                    else:
                        # Try to find dashboards store in LovelaceData attributes
                        for attr_name in dir(ll_data):
                            if not attr_name.startswith('_'):
                                attr_value = getattr(ll_data, attr_name)
                                if (hasattr(attr_value, "async_get") and 
                                    hasattr(attr_value, "async_create") and
                                    hasattr(attr_value, "async_update")):
                                    # Validate that attr_value is not a basic type before using it
                                    if not isinstance(attr_value, (dict, list, str, int, float, bool)):
                                        store = attr_value
                                        _LOGGER.debug("Found store in attribute '%s': %s", attr_name, type(attr_value).__name__)
                                        _LOGGER.debug("Assigned store from attribute '%s': %s (type: %s)", attr_name, store, type(store).__name__)
                                        break
                                    else:
                                        _LOGGER.debug("Skipping attribute '%s' - it's a basic type: %s", attr_name, type(attr_value).__name__)
                except Exception as e:
                    _LOGGER.debug("Failed to extract store from LovelaceData: %s", e)

        if store is None:
            # Handle different types of lovelace data structure
            ll_data = hass.data.get("lovelace")
            if ll_data is None:
                _LOGGER.warning("Lovelace dashboards API not available; no lovelace data found")
            elif hasattr(ll_data, 'keys'):
                # Older HA versions where lovelace data is a dict
                _LOGGER.warning(
                    "Lovelace dashboards API not available; keys in hass.data.lovelace=%s",
                    list(ll_data.keys()),
                )
            else:
                # Newer HA versions where lovelace data is a LovelaceData object
                _LOGGER.warning(
                    "Lovelace dashboards API not available; lovelace data type: %s, available attributes: %s",
                    type(ll_data).__name__,
                    [attr for attr in dir(ll_data) if not attr.startswith('_') and not callable(getattr(ll_data, attr, None))]
                )
                
                # Try one more approach for newer HA versions - check if we can use the LovelaceData directly
                try:
                    if hasattr(ll_data, "async_create_dashboard"):
                        # Validate that ll_data is not a basic type before using it
                        if not isinstance(ll_data, (dict, list, str, int, float, bool)):
                            _LOGGER.info("Found LovelaceData with async_create_dashboard method, attempting to use it directly")
                            store = ll_data
                            _LOGGER.debug("Assigned store from LovelaceData (async_create_dashboard): %s (type: %s)", store, type(store).__name__)
                        else:
                            _LOGGER.debug("Skipping LovelaceData (async_create_dashboard) - it's a basic type: %s", type(ll_data).__name__)
                    elif hasattr(ll_data, "dashboards") and hasattr(ll_data.dashboards, "async_create_dashboard"):
                        # Validate that dashboards is not a basic type before using it
                        if not isinstance(ll_data.dashboards, (dict, list, str, int, float, bool)):
                            _LOGGER.info("Found LovelaceData.dashboards with async_create_dashboard method")
                            store = ll_data.dashboards
                            _LOGGER.debug("Assigned store from LovelaceData.dashboards (async_create_dashboard): %s (type: %s)", store, type(store).__name__)
                        else:
                            _LOGGER.debug("Skipping LovelaceData.dashboards - it's a basic type: %s", type(ll_data.dashboards).__name__)
                        
                    # Try to find dashboard store in other attributes
                    if store is None:
                        for attr_name in ['dashboards', 'yaml_dashboards', 'resources']:
                            if hasattr(ll_data, attr_name):
                                attr_value = getattr(ll_data, attr_name)
                                _LOGGER.debug("Checking attribute '%s': %s (type: %s)", attr_name, attr_value, type(attr_value).__name__)
                                
                                # Only accept objects that are not basic types and have dashboard methods
                                if (not isinstance(attr_value, (dict, list, str, int, float, bool)) and
                                    (hasattr(attr_value, "async_get") or hasattr(attr_value, "async_get_dashboard"))):
                                    _LOGGER.info("Found potential dashboard store in attribute '%s': %s", attr_name, type(attr_value).__name__)
                                    store = attr_value
                                    _LOGGER.debug("Assigned store from attribute '%s': %s (type: %s)", attr_name, store, type(store).__name__)
                                    break
                                else:
                                    _LOGGER.debug("Skipping attribute '%s' - type: %s, has methods: %s", 
                                                 attr_name, type(attr_value).__name__,
                                                 hasattr(attr_value, "async_get") or hasattr(attr_value, "async_get_dashboard"))
                except Exception as e:
                    _LOGGER.debug("Failed to use LovelaceData directly: %s", e)
                    
            if store is None:
                return

        # Validate that the store has all required methods before proceeding
        _LOGGER.debug("Validating store object: %s (type: %s)", store, type(store).__name__)
        
        # Ensure store is not a basic type like dict, list, str, etc.
        if isinstance(store, (dict, list, str, int, float, bool)):
            _LOGGER.error("Store object is a basic type (%s), expected an object with dashboard methods", type(store).__name__)
            return
            
        _LOGGER.debug("Store attributes: %s", [attr for attr in dir(store) if not attr.startswith('_') and not callable(getattr(store, attr, None))])
        _LOGGER.debug("Store methods: %s", [attr for attr in dir(store) if not attr.startswith('_') and callable(getattr(store, attr, None))])
        
        # Check for various method name patterns that might exist
        has_get = (hasattr(store, "async_get") or 
                  hasattr(store, "async_get_dashboard") or
                  hasattr(store, "get") or
                  hasattr(store, "get_dashboard"))
        has_create = (hasattr(store, "async_create") or 
                    hasattr(store, "async_create_dashboard") or
                    hasattr(store, "create") or
                    hasattr(store, "create_dashboard"))
        has_update = (hasattr(store, "async_update") or 
                    hasattr(store, "async_update_dashboard") or
                    hasattr(store, "update") or
                    hasattr(store, "update_dashboard"))
        
        _LOGGER.debug("Method availability - get: %s, create: %s, update: %s", has_get, has_create, has_update)
        
        if not has_get:
            _LOGGER.error("Store object missing required 'get' method: %s", type(store).__name__)
            return
        if not has_create:
            _LOGGER.error("Store object missing required 'create' method: %s", type(store).__name__)
            return
        if not has_update:
            _LOGGER.error("Store object missing required 'update' method: %s", type(store).__name__)
            return
            
        # Compatibility for method names across HA versions
        get_method = getattr(store, "async_get", None) or getattr(store, "async_get_dashboard")
        create_method = getattr(store, "async_create", None) or getattr(store, "async_create_dashboard")
        update_method = getattr(store, "async_update", None) or getattr(store, "async_update_dashboard")
        
        # Additional method name checks for newer HA versions
        if get_method is None:
            get_method = getattr(store, "get", None)
        if create_method is None:
            create_method = getattr(store, "create", None)
        if update_method is None:
            update_method = getattr(store, "update", None)
            
        _LOGGER.debug("Found methods - get: %s, create: %s, update: %s", 
                     get_method.__name__ if get_method else None,
                     create_method.__name__ if create_method else None,
                     update_method.__name__ if update_method else None)

        # Check if we have all required methods
        if not all([get_method, create_method, update_method]):
            missing_methods = []
            if not get_method:
                missing_methods.append("get")
            if not create_method:
                missing_methods.append("create")
            if not update_method:
                missing_methods.append("update")
            _LOGGER.error("Missing required dashboard methods: %s", missing_methods)
            return

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
        save_method = None
        if hasattr(store, "async_save_config"):
            save_method = store.async_save_config
        elif hasattr(store, "async_save"):
            # Older/newer core versions use a shorter name
            save_method = store.async_save
        elif hasattr(store, "save_config"):
            # Some versions might use sync methods
            save_method = store.save_config
        elif hasattr(store, "save"):
            # Some versions might use sync methods
            save_method = store.save
            
        if save_method:
            try:
                if save_method.__name__.startswith("async_"):
                    await save_method(url_path=url_path, config=ll_config)
                else:
                    # Handle sync methods
                    save_method(url_path=url_path, config=ll_config)
            except Exception as e:
                _LOGGER.error("Failed to save dashboard config: %s", e)
                return
        else:
            _LOGGER.error("No supported save method found for LovelaceDashboards")
            return

        _LOGGER.info("Saved dashboard config for '%s'", url_path)
    except Exception as e:  # noqa: BLE001
        _LOGGER.exception("Failed to create/update Lovelace dashboard: %s", e)