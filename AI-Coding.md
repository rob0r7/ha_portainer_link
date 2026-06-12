# AI Coding Instructions

These instructions are mandatory for every AI/coding session in this repository.

## Session Startup

- Read this file before making changes.
- Check `git status --short --branch` before editing.
- Do not overwrite or revert user changes unless explicitly asked.
- If `.env` exists, inspect only key names and whether values are present. Never print, copy, commit, or summarize secret values.
- Keep `.env` ignored by git.

## Project Context

- This repository contains the `ha_portainer_link` Home Assistant custom integration.
- Integration code lives in `custom_components/ha_portainer_link/`.
- The integration monitors and controls Docker containers and stacks through Portainer.
- Network load is a major product constraint. Avoid designs that cause frequent DNS, registry, or Portainer API calls.

## Architecture Rules

- Use one `PortainerAPI` instance and one `PortainerDataUpdateCoordinator` per config entry.
- Platforms must read state from the coordinator. Do not create separate API sessions in `sensor.py`, `binary_sensor.py`, `switch.py`, `button.py`, or `update.py`.
- Entity classes should inherit shared helpers from `entity.py` where possible.
- Regular entity updates must not call Portainer directly.
- Only explicit user actions, such as switch toggles, buttons, and update installs, may perform write operations.
- Background update checks must never pull images. Pulling images is allowed only for explicit user-triggered update actions.
- Keep container and device identifiers stable across Docker container ID changes.
- Prefer entry ID, endpoint ID, host key, stack name, service name, and container name/number over Docker container IDs.
- Preserve entity unique IDs where possible through migrations when identifier formats change.
- Clean up stale empty devices defensively, but never remove devices that still have entities.

## Options Defaults

- Runtime behavior must be configurable through the Home Assistant options flow.
- Defaults should be conservative.
- Normal Portainer polling should use a moderate interval.
- Registry/update checks should be infrequent and cached by default.
- Explicit update actions should remain available when the related feature is enabled.

## Home Assistant Compatibility

- Follow Home Assistant custom integration patterns.
- Keep compatibility with Home Assistant 2023.8+ unless the minimum version is deliberately changed.
- Keep `services.yaml`, `manifest.json`, README, and CHANGELOG synchronized with implemented behavior.
- Avoid adding new dependencies unless necessary and documented.

## Testing And Verification

Run these checks after code changes:

```powershell
Get-ChildItem -LiteralPath .\custom_components\ha_portainer_link -Filter *.py | ForEach-Object { python -m py_compile $_.FullName }
git diff --check
```

When Home Assistant is available, also verify:

- Config flow accepts valid Portainer credentials and rejects invalid endpoint/credentials.
- Options flow shows runtime settings and reloads the entry.
- `ha_portainer_link.refresh` and `ha_portainer_link.reload` are available in Developer Tools.
- Stopped containers show uptime as not running/unknown instead of stale elapsed time.
- Update entities do not show false updates for `latest`, `lts`, or similar non-version tags.
- No background image pulls occur.
- Integration reload/unload does not leak aiohttp sessions.
- Container recreation does not leave empty stale devices.

## Documentation

- Update `README.md` and `CHANGELOG.md` when behavior, options, services, platforms, or defaults change.
- Keep documentation aligned with implemented behavior.
- Do not document services or options that are not registered.
- Do not include local `.env` values or private environment details in docs, logs, issues, commits, or PRs.
