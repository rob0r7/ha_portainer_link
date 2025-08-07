# HA Portainer Link

A Home Assistant custom integration to manage Docker containers via Portainer API.

## Features

- **Container Status Monitoring**: Real-time status, CPU, memory, and uptime sensors
- **Update Management**: Detect available updates and pull new images
- **Container Control**: Start, stop, and restart containers
- **Stack Management**: Manage Docker Compose stacks with dedicated controls
- **Version Tracking**: Monitor current and available versions of container images
- **Multi-Instance Support**: Manage multiple Portainer instances from a single Home Assistant installation

## Installation

1. Copy the `custom_components/ha_portainer_link` folder to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant
3. Go to **Settings** → **Devices & Services** → **Add Integration**
4. Search for "HA Portainer Link" and configure your Portainer instance

## Configuration

### Required Settings
- **Host**: Your Portainer instance URL (e.g., `http://192.168.1.100:9000`)
- **Endpoint ID**: The Docker endpoint ID in Portainer (usually `1` for local Docker)
- **Authentication**: Either username/password or API key

### Optional Settings
- **API Key**: Alternative to username/password authentication

## Troubleshooting

### Duplicate Stack Devices
If you see duplicate stack devices (e.g., "Stack: wekan (192.168.0.105)" appearing twice), this usually indicates you have multiple configuration entries for the same Portainer instance.

**Solution:**
1. Go to **Settings** → **Devices & Services**
2. Look for multiple "HA Portainer Link" entries
3. Remove the duplicate configuration entries, keeping only one per Portainer instance
4. Restart Home Assistant

### Containers Appearing as Standalone When They Should Be in Stacks
If containers that are part of a Docker Compose stack are appearing as standalone devices instead of being grouped under a stack device, this indicates a stack detection issue.

**Diagnosis:**
1. Enable debug logging for the integration:
   ```yaml
   logger:
     custom_components.ha_portainer_link: debug
   ```
2. Check the Home Assistant logs for stack detection messages
3. Look for messages like:
   - `🔍 Stack detection for container: stack_name=...`
   - `✅ Container is part of stack: ...`
   - `ℹ️ Container is standalone (no stack labels found)`

**Common Causes:**
- Container inspection API calls failing
- Missing Docker Compose labels
- Network connectivity issues to Portainer

**Solution:**
1. Verify Portainer API connectivity
2. Check that containers are properly deployed via Docker Compose
3. Ensure the `com.docker.compose.project` label is present on stack containers

### Enhanced Logging
Version 0.5.6 includes enhanced logging to help diagnose issues:
- Container processing details
- Stack detection results
- Device creation information
- API call success/failure status

To enable detailed logging, add to your `configuration.yaml`:
```yaml
logger:
  custom_components.ha_portainer_link: debug
```

## Roadmap

- [ ] Additional sensors (disk usage, network statistics)
- [ ] Service calls for container management
- [ ] Auto dashboard creation
- [ ] HACS default store integration

## Support

For issues and feature requests, please visit the [GitHub repository](https://github.com/rob0r7/ha_portainer_link).


