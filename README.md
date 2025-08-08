# HA Portainer Link

A comprehensive Home Assistant integration for managing Docker containers and stacks through Portainer.

## 🚀 Features

### Core Functionality
- **Container Management**: Start, stop, and restart individual containers
- **Stack Management**: Control entire Docker stacks (start, stop, update)
- **Real-time Monitoring**: Live status, CPU, memory, and uptime tracking
- **Automatic Discovery**: Automatically detects containers and stacks
- **SSL Support**: Automatic SSL certificate handling with fallback

### Integration Modes
- **Lightweight View**: Essential features only (switches, restart buttons, basic sensors)
- **Full View**: Complete functionality including update checks and version sensors

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
   - **Endpoint ID**: Usually `1` for local Docker, check Portainer → Endpoints
   - **Integration Mode**: Choose Lightweight or Full View

### Configuration Options

#### Lightweight View
- Container switches (start/stop)
- Restart buttons
- Status sensors
- CPU and memory monitoring
- Uptime tracking
- Stack controls

#### Full View
- All Lightweight features
- Update availability sensors
- Version tracking
- Bulk operations
- Advanced monitoring

## 🏗️ Architecture

### Components
- **PortainerAPI**: Main API facade with automatic SSL handling
- **DataUpdateCoordinator**: Centralized data management and caching
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
**Solution**: The integration automatically handles SSL issues. If problems persist, check your Portainer SSL configuration.

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

#### Stack Update Not Pulling New Images
**Solution**: The stack update function now performs a complete force update:
1. Pulls latest images for all containers
2. Stops all containers in the stack
3. Removes old containers
4. Redeploys with new images
5. This process may take several minutes for large stacks

### Debugging
Enable debug logging in your `configuration.yaml`:
```yaml
logger:
  ha_portainer_link: debug
```

## 🛠️ Services

### Available Services

#### `ha_portainer_link.reload`
Reload all Portainer integrations.

#### `ha_portainer_link.refresh`
Force refresh container data for all integrations.

## 📊 Sensors

### Container Sensors
- **Status**: Running, stopped, paused
- **CPU Usage**: Current CPU utilization
- **Memory Usage**: Current memory consumption
- **Uptime**: Container running time
- **Image**: Current image name and tag
- **Current Version**: Extracted version from image
- **Available Version**: Latest available version (Full View only)
- **Update Available**: Whether updates are available (Full View only)

### Stack Sensors
- **Status**: Overall stack status
- **Container Count**: Number of containers in stack

## 🔘 Switches & Buttons

### Container Controls
- **Container Switch**: Start/stop individual containers
- **Restart Button**: Restart container
- **Pull Update Button**: Pull latest image (Full View only)

### Stack Controls
- **Stack Start**: Start entire stack
- **Stack Stop**: Stop entire stack
- **Stack Update**: Force update stack with image pull and container recreation

### Bulk Operations (Full View only)
- **Start All**: Start all stopped containers
- **Stop All**: Stop all running containers

## 🔄 Recent Updates

### v0.3.4 (Current)
- 🔧 Fixed migration handler for config entries from older versions
- 🔧 Added missing services.yaml file for proper service registration
- 🔧 Cleaned up unused imports to reduce log noise
- 🔧 Enhanced migration to handle all version upgrades properly

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

### v0.3.0
- Complete rewrite with modern Home Assistant patterns
- Added stack clustering and organization
- Implemented comprehensive error handling

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

---

**Note**: This is a custom integration and not officially supported by Home Assistant. Use at your own risk.


