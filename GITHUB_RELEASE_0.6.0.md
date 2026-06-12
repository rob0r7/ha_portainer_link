# HA Portainer Link 0.6.0

This release stabilizes the integration around Home Assistant's coordinator model and fixes the update-detection and network-traffic issues reported in the open issue set.

## Highlights

- One shared Portainer API/session and one data coordinator per config entry.
- Coordinator-backed sensors, binary sensors, switches, buttons, and update entities.
- Native Home Assistant `update` entities for container image updates.
- Real options flow for feature toggles, polling intervals, update-check intervals, SSL verification, and notification target.
- Working `ha_portainer_link.reload` and `ha_portainer_link.refresh` services.
- Stable entity and device identifiers that survive Docker container recreation.
- Stale empty device cleanup after container recreate/update.
- Digest-based update detection with multi-architecture manifest handling.
- No background image pulls during update checks.
- Fixed stopped-container uptime reporting.
- Fixed Home Assistant 2026 options-flow compatibility.

## Network Behavior

- Normal Portainer polling defaults to every 5 minutes.
- Registry/update checks default to every 360 minutes.
- Background checks only inspect metadata and never pull images.
- Explicit update actions still pull/recreate when triggered by the user.

## Validation

- `python -m py_compile` for all integration Python files.
- `git diff --check`.
- Copied to a Home Assistant test instance and hash-verified.
- Home Assistant config flow and options flow verified with HTTP 200.
- `ha_portainer_link.refresh` verified in the Home Assistant test instance.

## Upgrade Notes

After upgrading, restart Home Assistant. If update entities are not visible immediately, open the integration options and verify that **Update sensors** are enabled, then call `ha_portainer_link.refresh`.
