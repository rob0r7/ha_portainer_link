# HA Portainer Link

A Home Assistant custom integration to manage Docker containers via Portainer API.

## Features

- **Container Status Monitoring**: Real-time status, CPU, memory, and uptime sensors
- **Container Control**: Start, stop, and restart containers with automatic state synchronization
- **Stack Management**: Manage Docker Compose stacks with dedicated controls (start, stop, force update)
- **Stack Clustering**: Automatic grouping of stack containers under unified devices
- **Version Tracking**: Monitor current and available versions of container images
- **Update Detection**: Smart update availability detection with conservative rate limiting
- **Multi-Instance Support**: Manage multiple Portainer instances from a single Home Assistant installation
- **Rate Limit Protection**: Smart caching and API call optimization to avoid Docker Hub rate limits

### Stack Clustering
The integration automatically detects and groups containers that belong to Docker Compose stacks:
- **Stack Containers**: Grouped under a single "Stack: StackName" device
- **Standalone Containers**: Each container gets its own device
- **Automatic Detection**: Uses Docker Compose labels to identify stack membership
- **Stable Entity IDs**: Entities maintain their identity even when containers are recreated

### Container State Synchronization
- **Real-time Updates**: Container switches automatically reflect current state
- **Stack Operations**: Starting/stopping stacks updates all related container switches
- **Coordinator Pattern**: Efficient data fetching and caching for optimal performance

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

### Docker Hub Rate Limits
The integration includes built-in protection against Docker Hub rate limits:
- **Conservative Rate Limiting**: Maximum 50 checks per 6 hours (well under the 100 limit for anonymous users)
- **Smart Caching**: Results are cached for 6 hours to minimize API calls
- **Update Detection**: Re-enabled with proper rate limiting and caching
- **Automatic Fallback**: Uses cached results when rate limits are reached
- **Manual Updates**: Pull update buttons still work when manually triggered

### Stack Clustering Issues
If containers that are part of a Docker Compose stack are appearing as standalone devices:

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

### Container State Not Updating
If container switches don't reflect the current state after stack operations:

**Solution:**
1. The integration now automatically refreshes data after operations
2. Small delays are built-in to ensure data propagation
3. Check logs for coordinator refresh messages

### Duplicate Stack Devices
If you see duplicate stack devices, this usually indicates multiple configuration entries for the same Portainer instance.

**Solution:**
1. Go to **Settings** → **Devices & Services**
2. Look for multiple "HA Portainer Link" entries
3. Remove the duplicate configuration entries, keeping only one per Portainer instance
4. Restart Home Assistant

To enable detailed logging, add to your `configuration.yaml`:
```yaml
logger:
  custom_components.ha_portainer_link: debug
```

## Roadmap

- [ ] Docker Hub API integration for update detection
- [ ] Additional sensors (disk usage, network statistics)
- [ ] Service calls for container management
- [ ] Auto dashboard creation
- [ ] HACS default store integration

## Recent Updates

### Version 0.3.0 (Current)
- ✅ **Major Architectural Refactoring**: Implemented Home Assistant DataUpdateCoordinator pattern
- ✅ **Modular API Design**: Split monolithic API into specialized classes (Auth, Container, Stack, Image)
- ✅ **Base Entity Classes**: Reduced code duplication with shared base classes
- ✅ **Improved Stack Clustering**: Enhanced stack detection and device grouping
- ✅ **Conservative Rate Limiting**: Smart rate limiting with 50 checks per 6 hours (well under Docker Hub limits)
- ✅ **Update Detection Re-enabled**: Update availability sensors now work with proper rate limiting
- ✅ **Container State Synchronization**: Automatic state updates after stack operations
- ✅ **Enhanced Error Handling**: Better validation and user feedback
- ✅ **Optimized Update Frequency**: 5-minute intervals for good balance between responsiveness and rate limiting
- ✅ **6-Hour Caching**: Extended cache duration to minimize API calls

### Version 0.2.10
- ✅ **Re-enabled Update Detection**: Binary sensors for update availability are now active again
- ✅ **Update Status Monitoring**: Users can see when updates are available for their containers
- ⚠️ **Update Buttons Still Disabled**: Individual and stack update buttons remain disabled for safety
- ✅ **Best of Both Worlds**: Update awareness without the risk of problematic update operations

### Version 0.2.9
- ⚠️ **Temporarily Disabled Update Features**: All update and upgrade buttons have been disabled due to ongoing issues
- ⚠️ **Disabled Update Sensors**: Binary sensors for update availability are now disabled
- ⚠️ **Disabled Pull Update Buttons**: Individual container update buttons are disabled
- ⚠️ **Disabled Stack Force Update**: Stack-level force update buttons are disabled
- ✅ **Maintained Core Functionality**: All other features (status, CPU, memory, power controls) remain fully functional

### Version 0.2.8
- ✅ **Improved Entity Naming**: Implemented cleaner, shorter naming scheme for all entities
- ✅ **Consistent Naming Pattern**: All entities now follow `<Type> <Name>` format (e.g., "Status filebrowser", "CPU mariadb")
- ✅ **Stack Container Naming**: Stack containers use `<Type> <Service> (<Stack>)` format (e.g., "Status db (pastefy)")
- ✅ **Reduced Verbosity**: Eliminated redundant words like "Usage", "Container", "Docker" from entity names
- ✅ **Better UI Experience**: Much cleaner and more readable entity names in Home Assistant interface

### Version 0.2.7
- ✅ **Fixed Container ID Update Mechanism**: Corrected function signature and task creation for periodic container ID updates
- ✅ **Stable Entity IDs**: Implemented stable entity identification that doesn't change when containers are recreated
- ✅ **Container ID Auto-Update**: Added automatic detection and update of container IDs when containers are recreated
- ✅ **Persistent Device Associations**: Entities now maintain their device associations even after container recreation
- ✅ **Enhanced Entity Stability**: All sensors, switches, and buttons now use stable identifiers based on container names and stack information
- ✅ **Automatic Container Tracking**: Periodic background checks ensure entities stay synchronized with actual container instances

### Version 0.2.6

### Version 0.2.5
- ✅ **Fixed Stack Update API Endpoint**: Corrected the API endpoint from `/api/stacks/{id}/update` to `/api/stacks/{id}?endpointId={id}&type=2`
- ✅ **Added Type Parameter**: Added `type=2` parameter for Docker Compose stacks in the update request
- ✅ **Enhanced Stack Environment Variables**: Added support for environment variables in stack updates (UID, GID, etc.)
- ✅ **Improved Stack Details Retrieval**: Enhanced stack update to fetch actual environment variables from Portainer
- ✅ **Better Default Environment Handling**: Added fallback to default UID/GID values when environment variables are not found
- ✅ **Enhanced Debug Logging**: Added detailed logging for environment variables and payload structure

### Version 0.2.4

### Version 0.2.3
- ✅ **Enhanced Stack Force Update Logging**: Added comprehensive debug logging for all API calls and responses
- ✅ **Improved Stack Matching**: Enhanced stack search to match both name and endpoint ID for accuracy
- ✅ **Better Error Handling**: Added detailed error messages with HTTP status codes and response text
- ✅ **Stack File Content Validation**: Added validation and preview of stack file content before update

### Version 0.2.2
- ✅ **Fixed Stack Force Update API**: Corrected to use proper Portainer API endpoints (`/api/stacks/{id}/update?endpointId={id}`)
- ✅ **Fixed Request Payload**: Updated to use correct field names (`PullImage`, `Prune`) and removed invalid `endpointId` from body
- ✅ **Fixed Stack File Retrieval**: Corrected endpoint to `/api/stacks/{id}/file`
- ✅ **Enhanced Stack Filtering**: Properly filter stacks by endpoint ID

### Version 0.2.1
- ✅ **Fixed Stack Force Update**: Corrected API endpoints to use endpoint-specific URLs
- ✅ **Enhanced Stack API Calls**: Updated all stack operations to use `/api/endpoints/{endpoint_id}/stacks/` endpoints
- ✅ **Improved Error Handling**: Better debugging information for stack update failures

### Version 0.2.0
- ✅ **Update Available Sensor**: Detect if a new image version is available for containers
- ✅ **Pull Update Button**: Pull newer images and recreate/update containers with config persistence
- ✅ **Version Sensors**: Display current and available image versions
- ✅ **Container Control**: Start, stop, and restart individual containers
- ✅ **Stack Management**: Group containers belonging to Docker Compose stacks under single devices
- ✅ **Stack Force Update**: Complete stack updates with image pulling and redeployment
- ✅ **Multi-Portainer Support**: Unique device and entity identification across multiple instances
- ✅ **Enhanced Error Handling**: Comprehensive logging and user feedback for all operations
- ✅ **Device Organization**: Proper grouping of stack vs standalone containers
- ✅ **Debug Logging**: Detailed troubleshooting information for API calls and operations

## Support

For issues and feature requests, please visit the [GitHub repository](https://github.com/rob0r7/ha_portainer_link).


