# HA Portainer Link

A comprehensive Home Assistant integration for managing Docker containers and stacks through Portainer.

## 🚀 Features

### Core Functionality
- **Container Management**: Start, stop, and restart individual containers
- **Stack Management**: Control entire Docker stacks (start, stop, update) - enabled by default
- **Real-time Monitoring**: Live status, CPU, memory, and uptime tracking - enabled by default
- **Automatic Discovery**: Automatically detects containers and stacks
- **SSL Support**: SSL disabled by default (ssl=False) for self-signed certificates

### Feature Toggles
**Note**: Feature toggles are currently hardcoded in the configuration and cannot be changed without modifying the code.

- **Stack View**: Stack clustering and management (enabled by default)
- **Resource Sensors**: CPU, memory, and uptime monitoring (enabled by default)
- **Version Sensors**: Current and available version tracking (enabled by default)
- **Update Sensors**: Update availability detection (enabled by default)
- **Stack Buttons**: Stack control buttons (start, stop, update) (enabled by default for stack containers)
- **Container Buttons**: Container control buttons (restart, pull update) - Always enabled by default

### Device Organization
- **Hierarchical Structure**: Organized by stacks and containers
- **Smart Grouping**: Automatic stack detection and container grouping
- **Clean UI**: Clear separation between container and stack controls

## 📋 Requirements

- Home Assistant 2023.8.0 or newer
- Portainer CE/EE with API access
- Network connectivity between Home Assistant and Portainer

## 🔧 Installation

### Option 1: HACS (Recommended)
1. Install [HACS](https://hacs.xyz/) if you haven't already
2. Add this repository as a custom repository in HACS
3. Search for "HA Portainer Link" and install it
4. Restart Home Assistant

### Option 2: Manual Installation
1. Download the `custom_components/ha_portainer_link` folder
2. Copy it to your `config/custom_components/` directory
3. Restart Home Assistant

## ⚙️ Configuration

### Initial Setup
1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "HA Portainer Link"
4. Enter your Portainer details:
   - **Portainer URL**: Full URL (e.g., `https://192.168.1.100:9443`)
   - **Username/Password** or **API Key**: Your Portainer credentials
   - **Endpoint ID**: **Important!** Check your Portainer URL - if you see `https://192.168.1.100:9443/#!/1/docker/containers` then your endpoint ID is `1`. If you see `#!/2/docker/containers` then it's `2`, etc.
   
   **Note**: Feature toggles and update intervals are not configurable during initial setup in the current version.

**💡 Pro Tip**: Look at your Portainer URL when you're viewing containers. The number after `#!/` is your endpoint ID!

### Configuration Options

#### Basic Features (Always Available)
- Container switches (start/stop)
- Status sensors
- Basic container information
- Container buttons (restart, pull update)

#### Optional Features (Currently Hardcoded)
- **Stack View**: Stack clustering and management (enabled by default)
- **Resource Sensors**: CPU, memory, and uptime monitoring (enabled by default)
- **Version Sensors**: Current and available version tracking (enabled by default)
- **Update Sensors**: Update availability detection (enabled by default)
- **Stack Buttons**: Stack control buttons (enabled by default for stack containers)

**Note**: Most features are enabled by default. Only Stack View clustering is disabled by default. To change these defaults, you need to modify the configuration in the coordinator.py file or wait for a future version with proper configuration options.

## 🏗️ Architecture

### Components
- **PortainerAPI**: Main API facade with SSL handling (hardcoded to ssl=False)
- **DataUpdateCoordinator**: Centralized data management with configurable update intervals
- **Modular API Classes**: Specialized classes for containers, stacks, and images
- **Base Entities**: Reusable entity classes with common functionality

### Device Hierarchy
```
Portainer Endpoint
├── Stack: my-app
│   ├── Container: web (switch, sensors, buttons)
│   ├── Container: db (switch, sensors, buttons)
│   └── Stack Controls (start, stop, update)
└── Standalone Container: monitoring (switch, sensors, buttons)
```

## 📊 Sensors

### Container Sensors
- **Status**: Running, stopped, paused
- **CPU Usage**: Current CPU utilization
- **Memory Usage**: Current memory consumption
- **Uptime**: Container running time
- **Image**: Current image name and tag
- **Current Version**: Extracted version from image
- **Available Version**: Latest available version (if enabled)
- **Update Available**: Whether updates are available (if enabled)
- **Current Digest**: Current image digest (first 12 characters of SHA256)
- **Available Digest**: Available image digest from registry (if enabled)

### Stack Sensors
- **Status**: Overall stack status
- **Container Count**: Number of containers in stack

## 🔘 Switches & Buttons

### Container Controls
- **Container Switch**: Start/stop individual containers
- **Restart Button**: Restart container (always enabled)
- **Pull Update Button**: Pull latest image (always enabled)

### Stack Controls
- **Stack Start**: Start entire stack (enabled by default for stack containers)
- **Stack Stop**: Stop entire stack (enabled by default for stack containers)
- **Stack Update**: Comprehensive update with image pulling, container recreation, and robust error handling (enabled by default for stack containers)

## 🛠️ Services

### Available Services

#### `ha_portainer_link.reload`
Reload all Portainer integrations.

#### `ha_portainer_link.refresh`
Force refresh container data for all integrations.

## 🔍 Troubleshooting

### Common Issues

#### Endpoint 404 Error
```
❌ Endpoint 1 not found (404)
```
**Solution**: Check your Portainer → Endpoints to find the correct endpoint ID.

#### SSL Certificate Errors
```
ssl.SSLCertVerificationError: certificate verify failed
```
**Solution**: The integration uses `ssl=False` by default to handle self-signed certificates. If you need SSL verification, you'll need to modify the code.

#### Logger Configuration Error
```
Invalid config for 'logger': 'custom_components.ha_portainer_link' is an invalid option
```
**Solution**: Use `ha_portainer_link: info` in your `configuration.yaml`, not `custom_components.ha_portainer_link`.

#### Container State Not Updating
**Solution**: The integration automatically refreshes data. If issues persist, use the refresh service:
```yaml
service: ha_portainer_link.refresh
```

#### Stack Update Process
**Note**: Stack updates now perform a comprehensive process:
1. Retrieves stack file content (docker-compose.yml) and environment variables
2. Stops all containers in the stack
3. Deletes existing containers to force recreation
4. Redeploys the stack with fresh images and current compose settings
5. Waits for containers to be running with configurable timeout
6. Includes robust error handling and fallback mechanisms
7. Provides detailed progress reporting and debugging information

### Debugging
Enable debug logging in your `configuration.yaml`:
```yaml
logger:
  logs:
    ha_portainer_link: debug
```

## 🔄 Recent Updates

### v0.4.0 (Current - August 11, 2024)
- 🚀 Completely reworked stack update functionality with improved architecture
- 🔧 Enhanced stack update with centralized request handling and SSL handling
- 🔧 Added comprehensive error handling with detailed result reporting
- 🔧 Improved user feedback with button state management and configurable timeouts
- 🔧 Enhanced logging and progress tracking with detailed step-by-step reporting
- 🔧 Fixed button success logic to properly handle fallback paths
- 🔧 Fixed connection validation to properly detect endpoint existence
- 🔧 Fixed critical session management issue that caused "Session is closed" errors
- 🔧 Fixed endpoint ID configuration to use configured endpoint instead of hardcoded endpoint 1
- 🔧 Added comprehensive session sharing across all API modules (containers, stacks, images)
- 🔧 Fixed constructor parameter mismatches that caused initialization errors
- 🔧 Fixed sensor method name error that caused update sensor failures
- 🔧 Added defensive programming to prevent KeyError in container recreation
- 🔧 Improved stack stop logic for fresh stacks
- 🔧 Fixed entity category errors for version sensors
- 🔧 Removed device registry warnings by eliminating via_device references
- 🔍 Added Current Digest and Available Digest sensors for better image version tracking
- 🔧 Fixed Docker Hub API detection to properly handle third-party images (like interaapps/pastefy)
- ⚙️ Added comprehensive feature toggle configuration system
- ⚙️ Added configurable update intervals (1-60 minutes)
- ⚙️ **Note**: Options flow for runtime configuration is not yet fully implemented

### v0.3.7
- 🔧 Fixed indentation error in stack update fallback logic
- 🔧 Simplified stack update error handling for better reliability
- 🔧 Enhanced debugging output for troubleshooting stack update issues

### v0.3.6
- 🔧 Fixed stack update recreation issue (containers deleted but not recreated)
- 🔧 Enhanced stack update process with proper file content retrieval
- 🔧 Added multiple fallback mechanisms for failed updates
- 🔧 Improved timing with cleanup delays and extended refresh cycles
- 🔧 Enhanced debugging and error recovery for stack operations

### v0.3.5
- ✅ Fixed device registry warnings
- ✅ Fixed config flow deprecation warnings
- ✅ Fixed binary sensor entity categories
- ✅ Improved container state handling
- ✅ Enhanced SSL certificate handling
- ✅ Simplified integration modes (Lightweight/Full)
- ✅ Better error messages and debugging
- ✅ Optimized performance and reduced log noise

### v0.3.4
- Added automatic SSL verification with fallback
- Improved error handling for connection issues
- Enhanced container state synchronization

### v0.3.3
- Simplified configuration to two modes
- Fixed container switch state synchronization
- Improved device hierarchy organization

### v0.3.2
- Added integration modes (Lightweight, Full, Custom)
- Implemented configurable update intervals
- Added Docker Hub rate limiting protection

### v0.3.1
- Refactored to modular API architecture
- Added DataUpdateCoordinator for better performance
- Implemented automatic container discovery
- Complete rewrite with modern Home Assistant patterns
- Added stack clustering and organization
- Implemented comprehensive error handling

## 🙌 How You Can Help Test

A lightweight checklist for volunteers to validate the integration end-to-end before releases. Please **use a non-critical Portainer environment** (or a throwaway stack) because these tests start/stop/redeploy containers and stacks.

### 0) Prerequisites (one-time)
- Home Assistant **2023.8.0+**
- Portainer CE/EE with API access; note your **Endpoint ID** (the number after `#!/` in Portainer's URL)
- Network connectivity from Home Assistant → Portainer

### 1) Install & Add the Integration
1. Install via **HACS** (custom repo) *or* copy `custom_components/ha_portainer_link` into `config/custom_components/`, then restart HA.
2. In HA: **Settings → Devices & Services → Add Integration → "HA Portainer Link."**
3. Enter:
   - **Portainer URL** (e.g., `https://<ip>:9443`)
   - **Username/Password** or **API key**
   - **Endpoint ID** from the Portainer URL (`#!/<id>/docker/...`)

**Expected:** A "Portainer Endpoint" device appears, with child devices for stacks/containers (if any).

### 2) Quick Sanity Checks
- **Discovery:** Containers/stacks appear automatically as devices/entities.
- **Sensors present:** status, uptime, image; and (by default) CPU, memory, version, digest, update flags.
- **Controls present:** container **switch** (start/stop), **Restart**, **Pull Update**; stack **Start/Stop/Update** on stack containers.

### 3) Sensor Validation
For one **standalone container** and one **stack container**, verify:
- **Status** changes between *running/stopped/paused* and matches Portainer.
- **Uptime** increases while running and resets after restart.
- **CPU/Memory** show activity under load.
- **Image/Version/Digest**:
  - *Current Version/Digest* reflect the running image.
  - If you publish a newer image/tag, check **Available Version/Digest** and **Update Available**.

### 4) Container Controls
Pick a low-risk container:
1. **Toggle the container switch OFF → ON.**  
   **Expected:** Portainer shows the same state; HA sensors update after the next refresh.
2. **Press "Restart."**  
   **Expected:** Short downtime; uptime resets; status returns to *running*.
3. **Press "Pull Update."** (if a newer tag exists)  
   **Expected:** Latest image pulled; version/digest sensors change on refresh; container restarts if needed.

### 5) Stack Controls (if you have stacks)
Use a small test stack (e.g., `nginx` + `whoami`). Then:
- **Start/Stop** the stack from HA.  
  **Expected:** all stack containers start/stop together; stack status reflects reality.
- **Update** the stack from HA.  
  This triggers the enhanced update flow (fetch compose + env, stop, delete, redeploy, wait, with fallbacks).  
  **Expected:** fresh containers are created with the latest images and the stack returns to *running*.

**Minimal demo stack (optional)**
```yaml
version: "3.8"
services:
  whoami:
    image: traefik/whoami:latest
    ports: ["8000:80"]
  nginx:
    image: nginx:alpine
    ports: ["8080:80"]
```
Deploy in Portainer, then test HA's Stack Start/Stop/Update buttons.

### 6) Services
In **Developer Tools → Services**:
- Call `ha_portainer_link.refresh`  
  **Expected:** entities refresh without errors; states/sensors re-pull from Portainer.
- (If you manage multiple endpoints) Call `ha_portainer_link.reload`  
  **Expected:** integrations reload cleanly.

### 7) Common Failure Scenarios (please test!)
- **Wrong Endpoint ID:** set an incorrect ID during setup.  
  **Expected:** clear error ("Endpoint … not found (404)") with guidance to fix.
- **SSL quirks:** self-signed certs should work (SSL verification disabled by default). If you enable verification manually, report any errors.
- **Logger config typo:** using `custom_components.ha_portainer_link` under `logger:` should error; fix to `ha_portainer_link: info`.
- **Stuck state:** if entities don't update after actions, call `ha_portainer_link.refresh` and re-check Portainer.

### 8) Performance & Stability
- Note the **update interval** you configured (current builds support 1–60 minutes).
- Observe HA responsiveness and CPU/memory while sensors update under container load; report any spikes or slowdowns.

### 9) What to Report (copy/paste)
Please include:
- **Environment:** HA version, Portainer version, endpoint type (Docker/Agent), Endpoint ID
- **Install method:** HACS/manual
- **What you tested:** e.g., "Container restart button on `my_app`" / "Stack update on `demo_stack`"
- **Expected vs actual:** what you clicked, what happened in HA and in Portainer
- **Logs:** enable debug and attach relevant snippets:
  ```yaml
  logger:
    logs:
      ha_portainer_link: debug
  ```
  Reproduce once and capture logs + timestamps.

**Tips**
- If a button appears to "do nothing," wait for the next coordinator refresh or run `ha_portainer_link.refresh`, then check Portainer directly.
- For update tests, ensure there *is* a newer image/tag; otherwise "Update Available" will remain false.

## ⚠️ Current Limitations

### What's Not Yet Implemented
- **Runtime Configuration**: Feature toggles and update intervals cannot be changed after installation
- **SSL Configuration**: SSL verification is hardcoded to `ssl=False`
- **Bulk Operations**: Start/stop all containers functionality is not implemented
- **Container Logs**: Log viewing functionality is not implemented
- **Health Monitoring**: Container health status tracking is not implemented
- **Backup Management**: Container/stack backup functionality is not implemented

### Workarounds
- To change feature toggles: Remove and re-add the integration with new settings
- To enable SSL verification: Modify the code in the respective API files
- To enable disabled features: Modify the configuration in `coordinator.py`

**Note**: This is a custom integration and not officially supported by Home Assistant. Use at your own risk.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/rob0r7/ha_portainer_link/issues)
- **Discussions**: [GitHub Discussions](https://github.com/rob0r7/ha_portainer_link/discussions)

## 🙏 Acknowledgments

- Portainer team for the excellent API
- Home Assistant community for the amazing platform
- All contributors and testers


